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
    isRefreshingToken: false,
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
    if (elements.playSelectedSongButton) {
      elements.playSelectedSongButton.addEventListener("click", handlePlaySelectedSong);
    }

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
      typeInfo: document.querySelector("[data-type-info]"),
      diversityWrap: document.querySelector("[data-diversity-wrap]"),
      diversityInput: document.querySelector("[data-diversity-input]"),
      diversityValue: document.querySelector("[data-diversity-value]"),
      status: document.querySelector("[data-status]"),
      searchButton: document.querySelector("[data-search-button]"),
      selectedSong: document.querySelector("[data-selected-song]"),
      selectedSongTitle: document.querySelector("[data-selected-song-title]"),
      selectedSongArtist: document.querySelector("[data-selected-song-artist]"),
      selectedSongSources: document.querySelector("[data-selected-song-sources]"),
      playSelectedSongButton: document.querySelector("[data-play-selected-song]"),
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

      // Extract preview URL for the selected song if it appears in recommendations
      if (data && Array.isArray(data.recommendations)) {
        const selectedSongInRecommendations = data.recommendations.find((song) => {
          const sameName = String(song.song_name).toLowerCase() === String(state.searchedSong.song_name).toLowerCase();
          const sameArtist = String(song.artist_name).toLowerCase() === String(state.searchedSong.artist_name).toLowerCase();
          return sameName && sameArtist;
        });
        if (selectedSongInRecommendations && selectedSongInRecommendations.pulse_play_preview_url) {
          state.searchedSong.pulse_play_preview_url = selectedSongInRecommendations.pulse_play_preview_url;
          // Update the player with the preview URL
          const elements = getElements();
          elements.audioPlayer.src = selectedSongInRecommendations.pulse_play_preview_url;
        }
      }

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
   * If a 401 error is received (token expired), it attempts to refresh the token
   * and retry the request once.
   */
  async function apiRequest(path, options, isRetry = false) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    const data = await parseJson(response);

    // Handle unauthorized errors (token expired or invalid)
    if (response.status === 401 && !isRetry) {
      const errorDetail = data?.detail || "";
      
      // Only attempt refresh for token-related errors
      if (errorDetail.includes("expired") || errorDetail.includes("token")) {
        // Prevent multiple simultaneous refresh attempts
        if (!state.isRefreshingToken) {
          state.isRefreshingToken = true;
          try {
            // Attempt to refresh the token
            const refreshSuccess = await refreshAccessToken();
            state.isRefreshingToken = false;
            
            if (refreshSuccess) {
              // Retry the original request with the new token
              return apiRequest(path, options, true);
            }
          } catch (error) {
            state.isRefreshingToken = false;
          }
        }
      }
    }

    if (!response.ok) {
      throw new Error(getErrorMessage(data, response.status));
    }

    return data;
  }

  /*
   * Attempts to refresh the access token using the refresh token.
   * Returns true if successful, false otherwise.
   */
  async function refreshAccessToken() {
    try {
      const refreshResponse = await fetch("/auth/refresh", {
        method: "GET",
        credentials: "include", // Include cookies
      });

      // If refresh succeeds, the new token will be set in the cookie
      if (refreshResponse.ok) {
        return true;
      }
      
      // If refresh fails, redirect to login
      if (refreshResponse.status === 303 || refreshResponse.status === 302) {
        window.location.href = "/auth/login?session=expired";
        return false;
      }
      
      return false;
    } catch (error) {
      return false;
    }
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
   * Disabled options are kept visible with an explanatory message.
   */
  function configureAvailableTypes(searchResult, elements) {
    const currentValue = elements.typeSelect.value;
    let hasDisabledOptions = false;
    let disabledReason = "";

    Array.from(elements.typeSelect.options).forEach((option) => {
      const config = RECOMMENDERS[option.value];
      const isAvailable =
        option.value === "content"
          ? searchResult.found_in_content_db
          : searchResult.found_in_collab_db && config.requiresCollab;

      option.disabled = !isAvailable;
      // Don't hide disabled options - keep them visible but disabled

      if (!isAvailable) {
        hasDisabledOptions = true;
        if (option.value === "content") {
          disabledReason = "Not found in Content Database.";
        } else if (option.value === "collaborative") {
          disabledReason = "Not found in Collaborative Database.";
        } else if (option.value === "hybrid") {
          disabledReason = "Not found in Collaborative Database (required for Hybrid).";
        }
      }
    });

    // Show info message if there are disabled options
    if (hasDisabledOptions && !searchResult.found_in_collab_db) {
      elements.typeInfo.hidden = false;
      elements.typeInfo.textContent =
        "ℹ️ This song is only available in the Content Database. Collaborative and Hybrid filtering require the Collaborative Database.";
    } else {
      elements.typeInfo.hidden = true;
    }

    // Auto-switch if current selection is disabled
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

    // Mirror the selected song in the player panel (right side)
    elements.player.hidden = false;
    elements.playerTitle.textContent = searchResult.song_name;
    elements.playerArtist.textContent = searchResult.artist_name;
    try {
      elements.audioPlayer.removeAttribute("src");
      elements.audioPlayer.load();
    } catch (e) {
      // ignore if audio element not ready
    }
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

    // Filter out the currently selected song (if any) so it does not appear
    // in the recommendation list
    const filtered = data.recommendations.filter((song) => {
      if (!state.searchedSong) return true;
      try {
        const sameName = String(song.song_name).toLowerCase() === String(state.searchedSong.song_name).toLowerCase();
        const sameArtist = String(song.artist_name).toLowerCase() === String(state.searchedSong.artist_name).toLowerCase();
        return !(sameName && sameArtist);
      } catch (e) {
        return true;
      }
    });

    elements.resultsTitle.textContent = `${filtered.length} ${data.filter_type} recommendations`;

    filtered.forEach((song, index) => {
      const item = document.createElement("li");
      item.className = "recommendation-item";

      const left = document.createElement("div");
      left.className = "recommendation-left";

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
      left.append(rank, details);

      const preview = document.createElement("button");
      preview.className = "recommendation-preview";
      preview.type = "button";
      preview.textContent = song.pulse_play_preview_url ? "Play" : "No preview";
      preview.disabled = !song.pulse_play_preview_url;
      preview.addEventListener("click", () => {
        playPreview(song, elements);
      });

      item.append(left, preview);

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
   * Plays the originally selected song when the user clicks the play button
   * in the selected song card.
   */
  function handlePlaySelectedSong() {
    if (!state.searchedSong || !state.searchedSong.pulse_play_preview_url) {
      showStatus("No preview is available for this song.", "error");
      return;
    }

    const elements = getElements();
    playPreview(state.searchedSong, elements);
  }

  /*
   * Sets the page back to its initial results state.
   */
  function showEmptyState() {
    const elements = getElements();

    elements.selectedSong.hidden = true;
    elements.player.hidden = false;
    elements.playerTitle.textContent = "Pick a recommendation";
    elements.playerArtist.textContent = "Preview audio appears here as soon as you choose a track.";
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
