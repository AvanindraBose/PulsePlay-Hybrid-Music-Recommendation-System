/*
 * Pulse Play recommendation UI
 *
 * This file only handles browser behavior:
 * - read form values
 * - call the existing recommendation APIs
 * - update the page with loading, errors, song details, and recommendations
 *
 * HTML owns the layout. CSS owns the visual design. JavaScript only connects
 * the page to the backend.
 */
(function () {
  "use strict";

  const API_BASE = "/api";

  const RECOMMENDERS = {
    content: {
      label: "Content",
      endpoint: "/recommend/content",
      requiresCollab: false,
    },
    collaborative: {
      label: "Collaborative",
      endpoint: "/recommend/collaborative",
      requiresCollab: true,
    },
    hybrid: {
      label: "Hybrid",
      endpoint: "/recommend/hybrid",
      requiresCollab: true,
    },
  };

  const state = {
    searchedSong: null,
    isLoading: false,
  };

  document.addEventListener("DOMContentLoaded", initRecommendationPage);

  /*
   * Starts the page behavior after the HTML has loaded.
   * If this script is loaded on a page without the recommendation form, it exits
   * quietly so the same static file can be included safely.
   */
  function initRecommendationPage() {
    const form = document.querySelector("[data-recommendation-form]");

    if (!form) {
      return;
    }

    const elements = getElements();

    form.addEventListener("submit", handleSearchSubmit);
    elements.typeSelect.addEventListener("change", handleRecommendationTypeChange);
    elements.countSelect.addEventListener("change", refetchWhenSongExists);
    elements.diversityInput.addEventListener("input", handleDiversityInput);
    elements.diversityInput.addEventListener("change", refetchWhenSongExists);
    elements.songInput.addEventListener("input", resetRecommendationState);
    elements.artistInput.addEventListener("input", resetRecommendationState);

    handleDiversityInput();
    showEmptyState();
  }

  /*
   * Collects DOM elements in one place. This keeps the rest of the code readable
   * because functions can use clear names like elements.status instead of
   * repeating querySelector calls everywhere.
   */
  function getElements() {
    return {
      form: document.querySelector("[data-recommendation-form]"),
      songInput: document.querySelector("[data-song-input]"),
      artistInput: document.querySelector("[data-artist-input]"),
      countSelect: document.querySelector("[data-count-select]"),
      typeSelect: document.querySelector("[data-type-select]"),
      diversityWrap: document.querySelector("[data-diversity-wrap]"),
      diversityInput: document.querySelector("[data-diversity-input]"),
      diversityValue: document.querySelector("[data-diversity-value]"),
      status: document.querySelector("[data-status]"),
      searchButton: document.querySelector("[data-search-button]"),
      selectedSong: document.querySelector("[data-selected-song]"),
      selectedSongTitle: document.querySelector("[data-selected-song-title]"),
      selectedSongArtist: document.querySelector("[data-selected-song-artist]"),
      selectedSongSources: document.querySelector("[data-selected-song-sources]"),
      player: document.querySelector("[data-player]"),
      playerTitle: document.querySelector("[data-player-title]"),
      playerArtist: document.querySelector("[data-player-artist]"),
      audioPlayer: document.querySelector("[data-audio-player]"),
      resultsTitle: document.querySelector("[data-results-title]"),
      resultsList: document.querySelector("[data-results-list]"),
    };
  }

  /*
   * Handles the main form submit:
   * 1. validate song + artist
   * 2. confirm the song exists via search API
   * 3. render the selected song details
   * 4. fetch recommendations for the selected recommendation type
   */
  async function handleSearchSubmit(event) {
    event.preventDefault();

    const elements = getElements();
    const values = getFormValues(elements);
    const validationError = validateSearch(values);

    if (validationError) {
      showStatus(validationError, "error");
      return;
    }

    setLoading(true, "Searching for that song...");

    try {
      const searchResult = await searchSong(values.songName, values.artistName);

      state.searchedSong = searchResult;
      configureAvailableTypes(searchResult, elements);
      renderSelectedSong(searchResult, elements);
      await fetchAndRenderRecommendations();
    } catch (error) {
      state.searchedSong = null;
      showEmptyState();
      showStatus(error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  /*
   * Searches for a song. The backend route currently implemented in this repo is
   * /api/song/search.
   */
  async function searchSong(songName, artistName) {
    const params = new URLSearchParams({
      song_name: songName,
      artist_name: artistName,
    });

    return apiRequest(`/song/search?${params.toString()}`);
  }

  /*
   * Fetches recommendations using whichever type the user selected.
   * Hybrid receives one extra field: diversity.
   */
  async function fetchAndRenderRecommendations() {
    if (!state.searchedSong) {
      return;
    }

    const elements = getElements();
    const values = getFormValues(elements);
    const recommender = RECOMMENDERS[values.type];

    if (!recommender) {
      showStatus("Choose a valid recommendation type.", "error");
      return;
    }

    setLoading(true, "Loading recommendations...");

    const payload = {
      song_name: state.searchedSong.song_name,
      artist_name: state.searchedSong.artist_name,
      k: values.count,
    };

    if (values.type === "hybrid") {
      payload.diversity = values.diversity;
    }

    try {
      const data = await apiRequest(recommender.endpoint, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      renderRecommendations(data, elements);
      showStatus("", "");
    } catch (error) {
      renderRecommendations(null, elements);
      showStatus(error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  /*
   * Shared fetch helper for all API calls.
   * It parses JSON safely and turns backend error responses into normal
   * JavaScript Error objects, so calling functions can use one try/catch style.
   */
  async function apiRequest(path, options) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    const data = await parseJson(response);

    if (!response.ok) {
      throw new Error(getErrorMessage(data, response.status));
    }

    return data;
  }

  /*
   * Reads JSON without crashing if the server sends an empty or non-JSON body.
   */
  async function parseJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  /*
   * FastAPI usually returns errors as { detail: "message" }. Validation errors
   * can return detail as an array, so this helper makes both readable.
   */
  function getErrorMessage(data, statusCode) {
    if (data && typeof data.detail === "string") {
      return data.detail;
    }

    if (data && Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg).join(" ");
    }

    return `Request failed with status ${statusCode}.`;
  }

  /*
   * Reads and normalizes form fields. Number() converts select/range string
   * values into numbers before they are sent to FastAPI.
   */
  function getFormValues(elements) {
    return {
      songName: elements.songInput.value.trim(),
      artistName: elements.artistInput.value.trim(),
      count: Number(elements.countSelect.value),
      type: elements.typeSelect.value,
      diversity: Number(elements.diversityInput.value),
    };
  }

  /*
   * Simple frontend validation. Backend validation still runs too, but this
   * gives the user immediate feedback before a network request is made.
   */
  function validateSearch(values) {
    if (!values.songName || !values.artistName) {
      return "Enter both a song name and an artist name.";
    }

    if (!Number.isInteger(values.count) || values.count < 1 || values.count > 20) {
      return "Choose between 1 and 20 recommendations.";
    }

    return "";
  }

  /*
   * Shows only recommendation types that the searched song can support.
   * Content works when the song exists in the content database. Collaborative
   * and hybrid need the collaborative database.
   */
  function configureAvailableTypes(searchResult, elements) {
    const currentValue = elements.typeSelect.value;

    Array.from(elements.typeSelect.options).forEach((option) => {
      const config = RECOMMENDERS[option.value];
      const isAvailable =
        option.value === "content"
          ? searchResult.found_in_content_db
          : searchResult.found_in_collab_db && config.requiresCollab;

      option.disabled = !isAvailable;
      option.hidden = !isAvailable;
    });

    if (!elements.typeSelect.querySelector(`option[value="${currentValue}"]:not(:disabled)`)) {
      elements.typeSelect.value = searchResult.found_in_collab_db ? "hybrid" : "content";
    }

    handleRecommendationTypeChange();
  }

  /*
   * Shows/hides the diversity slider. Only hybrid recommendations use it.
   */
  function handleRecommendationTypeChange() {
    const elements = getElements();
    const isHybrid = elements.typeSelect.value === "hybrid";

    elements.diversityWrap.hidden = !isHybrid;
    refetchWhenSongExists();
  }

  /*
   * Updates the text beside the diversity slider.
   */
  function handleDiversityInput() {
    const elements = getElements();
    const value = Number(elements.diversityInput.value);
    const labels = {
      1: "very similar",
      2: "similar",
      3: "mostly similar",
      4: "slightly varied",
      5: "balanced",
      6: "slightly diverse",
      7: "diverse",
      8: "more diverse",
      9: "very diverse",
      10: "most diverse",
    };

    elements.diversityValue.textContent = `${value} - ${labels[value]}`;
  }

  /*
   * Re-fetches recommendations after controls change, but only after a song has
   * already been searched successfully.
   */
  function refetchWhenSongExists() {
    if (state.searchedSong && !state.isLoading) {
      fetchAndRenderRecommendations();
    }
  }

  /*
   * Clears previous results when the user edits song or artist fields.
   */
  function resetRecommendationState() {
    state.searchedSong = null;
    showEmptyState();
    showStatus("", "");
  }

  /*
   * Displays the song confirmed by /api/song/search, including which databases
   * can serve recommendations for it.
   */
  function renderSelectedSong(searchResult, elements) {
    const sources = [];

    if (searchResult.found_in_content_db) {
      sources.push("Content");
    }

    if (searchResult.found_in_collab_db) {
      sources.push("Collaborative");
    }

    elements.selectedSong.hidden = false;
    elements.selectedSongTitle.textContent = searchResult.song_name;
    elements.selectedSongArtist.textContent = searchResult.artist_name;
    elements.selectedSongSources.textContent = sources.join(" + ");
  }

  /*
   * Renders recommendation rows. Text is assigned with textContent to avoid
   * injecting raw HTML from API data into the page.
   */
  function renderRecommendations(data, elements) {
    elements.resultsList.innerHTML = "";

    if (!data || !Array.isArray(data.recommendations) || data.recommendations.length === 0) {
      elements.resultsTitle.textContent = "No recommendations yet";
      return;
    }

    elements.resultsTitle.textContent = `${data.recommendations.length} ${data.filter_type} recommendations`;

    data.recommendations.forEach((song, index) => {
      const item = document.createElement("li");
      item.className = "recommendation-item";

      const rank = document.createElement("span");
      rank.className = "recommendation-rank";
      rank.textContent = String(index + 1);

      const details = document.createElement("div");
      details.className = "recommendation-details";

      const title = document.createElement("strong");
      title.textContent = song.song_name;

      const artist = document.createElement("span");
      artist.textContent = song.artist_name;

      details.append(title, artist);
      item.append(rank, details);

      const preview = document.createElement("button");
      preview.className = "recommendation-preview";
      preview.type = "button";
      preview.textContent = song.pulse_play_preview_url ? "Play" : "No preview";
      preview.disabled = !song.pulse_play_preview_url;
      preview.addEventListener("click", () => {
        playPreview(song, elements);
      });

      item.appendChild(preview);

      elements.resultsList.appendChild(item);
    });
  }

  /*
   * Plays a recommendation inside the dashboard instead of opening a new tab.
   * The browser's native <audio> element handles pause, seek, and volume.
   */
  function playPreview(song, elements) {
    if (!song.pulse_play_preview_url) {
      showStatus("No preview is available for this song.", "error");
      return;
    }

    elements.player.hidden = false;
    elements.playerTitle.textContent = song.song_name;
    elements.playerArtist.textContent = song.artist_name;
    elements.audioPlayer.src = song.pulse_play_preview_url;
    elements.audioPlayer.play().catch(() => {
      showStatus("The browser blocked autoplay. Press play in the audio player.", "error");
    });
  }

  /*
   * Sets the page back to its initial results state.
   */
  function showEmptyState() {
    const elements = getElements();

    elements.selectedSong.hidden = true;
    elements.player.hidden = true;
    elements.audioPlayer.removeAttribute("src");
    elements.audioPlayer.load();
    elements.resultsTitle.textContent = "Search for a song to begin";
    elements.resultsList.innerHTML = "";
  }

  /*
   * Shows validation errors, backend errors, and loading messages.
   */
  function showStatus(message, type) {
    const elements = getElements();

    elements.status.textContent = message;
    elements.status.hidden = !message;
    elements.status.className = type ? `recommendation-status ${type}` : "recommendation-status";
  }

  /*
   * Disables the submit button while requests are in flight so duplicate clicks
   * do not trigger overlapping API calls.
   */
  function setLoading(isLoading, message) {
    const elements = getElements();

    state.isLoading = isLoading;
    elements.searchButton.disabled = isLoading;
    elements.searchButton.textContent = isLoading ? "Please wait..." : "Get recommendations";

    if (isLoading && message) {
      showStatus(message, "loading");
    }
  }
})();
