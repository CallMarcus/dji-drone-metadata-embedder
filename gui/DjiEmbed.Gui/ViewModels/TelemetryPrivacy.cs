namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// What happens to GPS coordinates on the way into the copies. Covers every
/// command whose <c>--redact</c> accepts <c>none|drop|fuzz</c> (embed,
/// convert). Deliberately NOT <see cref="MapPrivacy"/>: <c>flightmap</c>/
/// <c>photomap</c> accept only <c>none|fuzz</c> and would reject <c>drop</c>.
/// One enum per redaction domain keeps each mode total over what its own CLI
/// accepts.
/// </summary>
public enum TelemetryPrivacy
{
    /// <summary>Coordinates pass through untouched (flag omitted).</summary>
    Keep,

    /// <summary>Coarsened to ~100 m (<c>--redact fuzz</c>).</summary>
    Fuzz,

    /// <summary>Removed entirely (<c>--redact drop</c>).</summary>
    Drop,
}

/// <summary>A selectable privacy stance: a label over a <see cref="TelemetryPrivacy"/>.
/// Separate from <see cref="PrivacyChoice"/>, which wraps <see cref="MapPrivacy"/>
/// and so cannot express the third stance <c>--redact</c> accepts.</summary>
public sealed record TelemetryPrivacyChoice(string Label, TelemetryPrivacy Value);
