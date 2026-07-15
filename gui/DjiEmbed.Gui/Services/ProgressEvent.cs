using System.Collections.Generic;
using System.Text.Json;

namespace DjiEmbed.Gui.Services;

public enum ProgressEventKind
{
    Start,
    Progress,
    Warning,
    Result,
    Error,

    /// <summary>
    /// A structurally valid event line whose type (or contract version) we
    /// do not interpret. Kept visible for diagnostics, never acted on.
    /// </summary>
    Unknown,
}

/// <summary>
/// One line of the dji-embed <c>--progress jsonl</c> stream
/// (docs/progress_jsonl.schema.json, contract v1).
/// </summary>
public sealed record ProgressEvent(
    ProgressEventKind Kind,
    string RawEventName,
    string? Command = null,
    int? Current = null,
    int? Total = null,
    string? Item = null,
    string? Message = null,
    bool? Ok = null,
    IReadOnlyList<string>? Outputs = null,
    JsonElement? Summary = null)
{
    private const int SupportedVersion = 1;

    /// <summary>
    /// Parses a single stdout line. Returns null when the line is not a
    /// JSON object with an "event" name — the caller records those as
    /// malformed rather than failing the run.
    /// </summary>
    public static ProgressEvent? Parse(string line)
    {
        JsonDocument doc;
        try
        {
            doc = JsonDocument.Parse(line);
        }
        catch (JsonException)
        {
            return null;
        }

        using (doc)
        {
            var root = doc.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("event", out var eventProp)
                || eventProp.ValueKind != JsonValueKind.String)
            {
                return null;
            }

            var name = eventProp.GetString()!;

            // A missing or bumped "v" means the field semantics may differ
            // from what this build understands: keep the event but do not
            // interpret it.
            if (!root.TryGetProperty("v", out var v)
                || v.ValueKind != JsonValueKind.Number
                || v.GetInt32() != SupportedVersion)
            {
                return new ProgressEvent(ProgressEventKind.Unknown, name);
            }

            return name switch
            {
                "start" => new ProgressEvent(ProgressEventKind.Start, name,
                    Command: GetString(root, "command"),
                    Total: GetInt(root, "total")),
                "progress" => new ProgressEvent(ProgressEventKind.Progress, name,
                    Current: GetInt(root, "current"),
                    Total: GetInt(root, "total"),
                    Item: GetString(root, "item")),
                "warning" => new ProgressEvent(ProgressEventKind.Warning, name,
                    Message: GetString(root, "message"),
                    Item: GetString(root, "item")),
                "result" => new ProgressEvent(ProgressEventKind.Result, name,
                    Ok: GetBool(root, "ok"),
                    Outputs: GetStringList(root, "outputs"),
                    Summary: root.TryGetProperty("summary", out var s)
                        ? s.Clone() : null),
                "error" => new ProgressEvent(ProgressEventKind.Error, name,
                    Message: GetString(root, "message"),
                    Item: GetString(root, "item")),
                _ => new ProgressEvent(ProgressEventKind.Unknown, name),
            };
        }
    }

    private static string? GetString(JsonElement root, string name) =>
        root.TryGetProperty(name, out var p) && p.ValueKind == JsonValueKind.String
            ? p.GetString() : null;

    private static int? GetInt(JsonElement root, string name) =>
        root.TryGetProperty(name, out var p) && p.ValueKind == JsonValueKind.Number
            ? p.GetInt32() : null;

    private static bool? GetBool(JsonElement root, string name) =>
        root.TryGetProperty(name, out var p)
        && p.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? p.GetBoolean() : null;

    private static IReadOnlyList<string>? GetStringList(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var p) || p.ValueKind != JsonValueKind.Array)
        {
            return null;
        }
        var items = new List<string>();
        foreach (var element in p.EnumerateArray())
        {
            if (element.ValueKind == JsonValueKind.String)
            {
                items.Add(element.GetString()!);
            }
        }
        return items;
    }
}
