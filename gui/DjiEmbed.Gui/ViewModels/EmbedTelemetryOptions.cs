namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// What happens to GPS coordinates on the way into the copies. Deliberately
/// NOT <see cref="MapPrivacy"/>: <c>embed --redact</c> accepts
/// <c>none|drop|fuzz</c>, while <c>flightmap</c>/<c>photomap</c> accept only
/// <c>none|fuzz</c> and would reject <c>drop</c>. One enum per command keeps
/// each mode total over what its own CLI accepts.
/// </summary>
public enum EmbedPrivacy
{
    /// <summary>Coordinates pass through untouched (flag omitted).</summary>
    Keep,

    /// <summary>Coarsened to ~100 m (<c>--redact fuzz</c>).</summary>
    Fuzz,

    /// <summary>Removed entirely (<c>--redact drop</c>).</summary>
    Drop,
}

/// <summary>
/// Immutable, typed state for an Embed telemetry run (GUI 2.0 spec, M3d). It
/// is the single input to <see cref="Services.CommandBuilder.Embed"/>, so the
/// argv is a pure function of this record — golden-testable. Every field maps
/// to an existing <c>embed</c> flag; the defaults reproduce M3a's bare argv.
/// <c>--overwrite</c> and <c>--dat PATH</c> are deliberately absent: both stay
/// CLI-only per the M3d spec.
/// </summary>
/// <param name="Container">A CLI container key: <c>mp4</c> (default) or
/// <c>mkv</c>, which preserves the DJI djmd/dbgi data streams the mp4 muxer
/// drops.</param>
/// <param name="ExtractHome">Write the launch point into the JSON sidecar
/// (<c>--extract-home</c>). Never written into the video, and redacted along
/// with everything else — <see cref="EmbedPrivacy.Drop"/> empties it.</param>
/// <param name="UseExifTool">Also write GPS metadata with ExifTool
/// (<c>--exiftool</c>) — the one field whose name does not mirror its
/// flag.</param>
/// <param name="DatAuto">Scan for DAT flight logs sitting beside the videos
/// and merge each match (<c>--dat-auto</c>). This is the whole DAT story in
/// the GUI: <c>--dat PATH</c>, which names one log for one video, stays
/// CLI-only.</param>
/// <param name="Output">Destination directory for the copies; empty means the
/// CLI default, a <c>processed</c> folder inside the source folder.</param>
public sealed record EmbedTelemetryOptions(
    EmbedPrivacy Privacy,
    string Container,
    bool ExtractHome,
    bool UseExifTool,
    bool AudioSidecar,
    bool DatAuto,
    string Output)
{
    public static readonly EmbedTelemetryOptions Defaults = new(
        Privacy: EmbedPrivacy.Keep,
        Container: "mp4",
        ExtractHome: false,
        UseExifTool: false,
        AudioSidecar: false,
        DatAuto: false,
        Output: "");
}
