from backend.schema.recommendation import Song

def _song_exists(df, song_name: str, artist_name: str) -> bool:
    return (
        (df["name"]   == song_name.lower()) &
        (df["artist"] == artist_name.lower())
    ).any()
 
 
def _df_to_songs(df) -> list[Song]:
    return [
        Song(
            song_name=row["name"].title(),
            artist_name=row["artist"].title(),
            pulse_play_preview_url=row.get("pulse_play_preview_url"),
        )
        for _, row in df.iterrows()
    ]