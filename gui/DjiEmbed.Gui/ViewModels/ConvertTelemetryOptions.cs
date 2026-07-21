namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Immutable, typed state for a Convert run (GUI 2.0 spec, M4a). Single
/// input to <see cref="Services.CommandBuilder.Convert"/>; the defaults
/// reproduce the bare argv (<c>convert gpx &lt;source&gt; [-b]</c>).
/// <c>--extract-home</c> stays CLI-only per the M4a spec.
/// </summary>
/// <param name="Format">A CLI format key: gpx (default), csv, geojson,
/// kml, html, cot.</param>
/// <param name="FootprintInterval">Seconds between footprint samples
/// (CLI default 2).</param>
/// <param name="Model">FOV-table key for footprints; empty = the CLI's
/// generic wide lens.</param>
/// <param name="CotInterval">cot only: seconds between sampled points
/// (CLI default 1).</param>
/// <param name="CotType">cot only: CoT event/affiliation code (CLI
/// default a-n-A, neutral air).</param>
/// <param name="Output">Single-file sources only: the output path; empty
/// means beside the source. Batch runs always write beside each source —
/// the CLI has no batch -o.</param>
public sealed record ConvertTelemetryOptions(
    string Format,
    TelemetryPrivacy Privacy,
    string TzOffset,
    bool Footprints,
    double FootprintInterval,
    string Model,
    double CotInterval,
    string CotType,
    string Output)
{
    public static readonly ConvertTelemetryOptions Defaults = new(
        Format: "gpx",
        Privacy: TelemetryPrivacy.Keep,
        TzOffset: "",
        Footprints: false,
        FootprintInterval: 2,
        Model: "",
        CotInterval: 1,
        CotType: "a-n-A",
        Output: "");
}
