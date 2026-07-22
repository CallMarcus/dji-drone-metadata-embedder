namespace DjiEmbed.Gui.ViewModels;

/// <summary>Which verification command a Verify run means (GUI 2.0 spec,
/// M4b): the mode merges check, validate and verify-sun behind one
/// sub-action switch.</summary>
public enum VerifySubAction
{
    Check,
    Validate,
    Sun,
}

/// <summary>
/// Immutable, typed state for a Verify run (GUI 2.0 spec, M4b). Single
/// input to <see cref="Services.CommandBuilder.Verify"/>; the defaults
/// reproduce the bare argv (<c>check &lt;source&gt;</c>).
/// </summary>
/// <param name="DriftThreshold">Validate only: seconds of SRT/MP4 drift
/// before the report flags a pair (CLI default 1.0).</param>
/// <param name="TzOffset">Sun check only: UTC offset of the clip's
/// timestamps; empty means the CLI's mtime auto-detect.</param>
public sealed record VerifyTelemetryOptions(
    VerifySubAction SubAction,
    double DriftThreshold,
    string TzOffset)
{
    public static readonly VerifyTelemetryOptions Defaults = new(
        SubAction: VerifySubAction.Check,
        DriftThreshold: 1.0,
        TzOffset: "");
}
