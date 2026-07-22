using System.Collections.Generic;
using System.Text.Json;

namespace DjiEmbed.Gui.Services;

/// <summary>How one Verify report row reads at a glance.</summary>
public enum VerifyStatus
{
    Ok,
    Attention,
    Failed,
}

/// <summary>One row of a Verify report. <paramref name="Detail"/> may be
/// empty — flag rows carry their whole sentence in the title.</summary>
public sealed record VerifyCard(
    VerifyStatus Status, string Title, string Detail);

/// <summary>
/// Turns a verify-family result summary into the novice-worded report the
/// done pane renders (GUI 2.0 spec, M4b: "reports as cards, never raw
/// text") — the <see cref="DoctorReport"/> pattern, one factory per
/// sub-action. A missing or malformed summary parses to
/// <see cref="Empty"/>, never a throw: report rendering must not be able
/// to fail a run that the CLI called successful.
/// </summary>
public sealed record VerifyReport(
    string Headline, IReadOnlyList<VerifyCard> Cards)
{
    public static readonly VerifyReport Empty = new("", []);

    /// <summary>`check`: {"checked": N, "files": {path: {gps, altitude,
    /// creation_time}}}. An empty per-file object is the CLI's
    /// couldn't-read marker (docs/PROGRESS_JSONL.md).</summary>
    public static VerifyReport FromCheck(JsonElement? summary)
    {
        if (summary is not { ValueKind: JsonValueKind.Object } s
            || !s.TryGetProperty("files", out var files)
            || files.ValueKind != JsonValueKind.Object)
        {
            return Empty;
        }
        var cards = new List<VerifyCard>();
        foreach (var file in files.EnumerateObject())
        {
            if (file.Value.ValueKind != JsonValueKind.Object)
            {
                continue;
            }
            var name = FileName(file.Name);
            var seen = false;
            foreach (var _ in file.Value.EnumerateObject())
            {
                seen = true;
                break;
            }
            if (!seen)
            {
                cards.Add(new VerifyCard(VerifyStatus.Failed, name,
                    "Couldn't read this file."));
                continue;
            }
            var gps = Flag(file.Value, "gps");
            var altitude = Flag(file.Value, "altitude");
            var time = Flag(file.Value, "creation_time");
            cards.Add(new VerifyCard(
                gps && altitude && time
                    ? VerifyStatus.Ok : VerifyStatus.Attention,
                name,
                $"GPS {Glyph(gps)} · Altitude {Glyph(altitude)} · "
                + $"Recording time {Glyph(time)}"));
        }
        var checkedCount = Int(s, "checked") ?? cards.Count;
        return new VerifyReport(
            checkedCount == 1
                ? "Checked 1 file" : $"Checked {checkedCount} files",
            cards);
    }

    /// <summary>`validate`: the full drift report. Issues and warnings
    /// become rows; the per-file analyses deliberately stay CLI-only
    /// (`validate --format json`).</summary>
    public static VerifyReport FromValidate(JsonElement? summary)
    {
        if (summary is not { ValueKind: JsonValueKind.Object } s)
        {
            return Empty;
        }
        var cards = new List<VerifyCard>();
        foreach (var issue in Strings(s, "issues"))
        {
            cards.Add(new VerifyCard(VerifyStatus.Attention, issue, ""));
        }
        foreach (var warning in Strings(s, "warnings"))
        {
            cards.Add(new VerifyCard(VerifyStatus.Attention, warning, ""));
        }
        var total = Int(s, "total_files") ?? 0;
        var valid = Int(s, "valid_pairs") ?? 0;
        var headline =
            total == 0 ? "No videos to validate"
            : cards.Count == 0 ? $"Everything pairs up — {valid} of {total}"
            : $"{valid} of {total} pairs check out";
        return new VerifyReport(headline, cards);
    }

    /// <summary>`verify-sun`: the sun summary dict. Stats become rows;
    /// the angular stats are null when nothing was computable, and the
    /// flags are translated out of their CLI names.</summary>
    public static VerifyReport FromSun(JsonElement? summary)
    {
        if (summary is not { ValueKind: JsonValueKind.Object } s)
        {
            return Empty;
        }
        var cards = new List<VerifyCard>();
        var points = Int(s, "points") ?? 0;
        var computed = Int(s, "sun_computed") ?? 0;
        cards.Add(new VerifyCard(VerifyStatus.Ok, "GPS points",
            $"{points} in the clip · {computed} with a computed sun position"));
        if (Str(s, "utc_start") is { } start && Str(s, "utc_end") is { } end)
        {
            cards.Add(new VerifyCard(VerifyStatus.Ok, "Time span (UTC)",
                $"{start} → {end}"));
        }
        if (Num(s, "elevation_min") is { } elMin
            && Num(s, "elevation_max") is { } elMax)
        {
            cards.Add(new VerifyCard(VerifyStatus.Ok, "Sun elevation",
                $"{elMin}° to {elMax}°"));
        }
        if (Num(s, "azimuth_start") is { } azStart
            && Num(s, "azimuth_end") is { } azEnd)
        {
            cards.Add(new VerifyCard(VerifyStatus.Ok,
                "Sun direction (azimuth)", $"{azStart}° → {azEnd}°"));
        }
        foreach (var flag in Strings(s, "flags"))
        {
            cards.Add(flag switch
            {
                "night" => new VerifyCard(VerifyStatus.Attention,
                    "Shot at night — the sun was below the horizon the "
                    + "whole time.", ""),
                "very_low_sun" => new VerifyCard(VerifyStatus.Attention,
                    "The sun was very low — long shadows, near sunrise "
                    + "or sunset.", ""),
                "sun_not_computable" => new VerifyCard(VerifyStatus.Failed,
                    "Couldn't work out the sun's position — the file has "
                    + "no usable timestamps.", ""),
                _ => new VerifyCard(VerifyStatus.Attention, flag, ""),
            });
        }
        var file = Str(s, "file");
        return new VerifyReport(
            file is null ? "Sun position" : $"Sun position over {file}",
            cards);
    }

    /// <summary>Last path segment after '/' or '\'. The CLI's summary
    /// paths are Windows paths regardless of the host OS running this
    /// code (dev/CI can be Linux), so this can't defer to
    /// <c>Path.GetFileName</c>, which only splits on the runtime
    /// platform's own separator.</summary>
    private static string FileName(string path)
    {
        var index = path.LastIndexOfAny(['/', '\\']);
        return index < 0 ? path : path[(index + 1)..];
    }

    private static bool Flag(JsonElement obj, string name) =>
        obj.TryGetProperty(name, out var p)
        && p.ValueKind == JsonValueKind.True;

    private static string Glyph(bool present) => present ? "✓" : "✗";

    private static int? Int(JsonElement obj, string name) =>
        obj.TryGetProperty(name, out var p)
        && p.ValueKind == JsonValueKind.Number
            ? p.GetInt32() : null;

    private static string? Str(JsonElement obj, string name) =>
        obj.TryGetProperty(name, out var p)
        && p.ValueKind == JsonValueKind.String
            ? p.GetString() : null;

    /// <summary>Raw JSON number text — the wire format is already
    /// invariant ("-8.1"), so the display never round-trips a double
    /// through a culture.</summary>
    private static string? Num(JsonElement obj, string name) =>
        obj.TryGetProperty(name, out var p)
        && p.ValueKind == JsonValueKind.Number
            ? p.GetRawText() : null;

    private static IEnumerable<string> Strings(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var arr)
            || arr.ValueKind != JsonValueKind.Array)
        {
            yield break;
        }
        foreach (var element in arr.EnumerateArray())
        {
            if (element.ValueKind == JsonValueKind.String)
            {
                yield return element.GetString()!;
            }
        }
    }
}
