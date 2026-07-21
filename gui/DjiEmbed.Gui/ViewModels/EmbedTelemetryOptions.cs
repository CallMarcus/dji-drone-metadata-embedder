namespace DjiEmbed.Gui.ViewModels;

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
/// with everything else — <see cref="TelemetryPrivacy.Drop"/> empties it.</param>
/// <param name="UseExifTool">Also write GPS metadata with ExifTool
/// (the flag is <c>--exiftool</c>, not <c>--use-exiftool</c>).</param>
/// <param name="DatAuto">Scan for a DAT flight log sitting beside each video
/// and merge whichever one matches (<c>--dat-auto</c>). This is the whole DAT
/// story in the GUI: <c>--dat PATH</c>, which forces a single log onto every
/// video in the folder, stays CLI-only.</param>
/// <param name="Output">Destination directory for the copies; empty means the
/// CLI default, a <c>processed</c> folder inside the source folder.</param>
public sealed record EmbedTelemetryOptions(
    TelemetryPrivacy Privacy,
    string Container,
    bool ExtractHome,
    bool UseExifTool,
    bool AudioSidecar,
    bool DatAuto,
    string Output)
{
    public static readonly EmbedTelemetryOptions Defaults = new(
        Privacy: TelemetryPrivacy.Keep,
        Container: "mp4",
        ExtractHome: false,
        UseExifTool: false,
        AudioSidecar: false,
        DatAuto: false,
        Output: "");
}
