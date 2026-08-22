using System;
using System.Text.Json;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// The <c>summary.update_check</c> block of <c>doctor --progress jsonl</c>
/// (docs/PROGRESS_JSONL.md, #319). <see cref="Consent"/> is doctor's own
/// remembered <c>--online/--offline</c> choice (null = never answered);
/// <see cref="Latest"/>/<see cref="Newer"/> are present only after an
/// explicit <c>--online</c> run and are null when the network was
/// unreachable — that is a non-event, never an error.
/// </summary>
public sealed record UpdateStatus(
    bool? Consent, bool HardDisabled, string? Current, string? Latest,
    bool? Newer, string? ReleasesUrl);

/// <summary>
/// The launch update note's pure parts (#319). The policy: the app may
/// look for a newer version at most once per <see cref="MinInterval"/>,
/// only with doctor's remembered consent, and it never downloads anything
/// — the note links to the release page, nothing more.
/// </summary>
public static class UpdateCheck
{
    public static readonly TimeSpan MinInterval = TimeSpan.FromHours(24);

    /// <summary>True when the app should run the probe now: never checked,
    /// checked at least <see cref="MinInterval"/> ago, or a last-check
    /// stamp from the future (clock jump) — a stale stamp must not silence
    /// the check forever.</summary>
    public static bool IsDue(DateTimeOffset? last, DateTimeOffset now) =>
        last is not { } l || now - l >= MinInterval || l - now > MinInterval;

    /// <summary>Null when the summary carries no block (an older CLI, a
    /// failed run): nothing to act on.</summary>
    public static UpdateStatus? Parse(JsonElement? summary)
    {
        if (summary is not { ValueKind: JsonValueKind.Object } s
            || !s.TryGetProperty("update_check", out var u)
            || u.ValueKind != JsonValueKind.Object)
        {
            return null;
        }
        return new UpdateStatus(
            Bool(u, "consent"),
            Bool(u, "hard_disabled") == true,
            Str(u, "current"),
            Str(u, "latest"),
            Bool(u, "newer"),
            Str(u, "releases_url"));
    }

    private static bool? Bool(JsonElement o, string name) =>
        o.TryGetProperty(name, out var v) ? v.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            _ => null,
        } : null;

    private static string? Str(JsonElement o, string name) =>
        o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String
            ? v.GetString() : null;
}
