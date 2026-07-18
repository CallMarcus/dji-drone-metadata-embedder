using System.Collections.Generic;
using System.Text.Json;

namespace DjiEmbed.Gui.Services;

/// <summary>One row of the setup checklist.</summary>
public sealed record SetupItem(string Label, bool Present, string? Detail);

/// <summary>Turns the doctor result summary into a novice-worded checklist.</summary>
public static class DoctorReport
{
    public static IReadOnlyList<SetupItem> Parse(JsonElement? summary)
    {
        var items = new List<SetupItem>();
        if (summary is not { ValueKind: JsonValueKind.Object } s
            || !s.TryGetProperty("tools", out var tools)
            || tools.ValueKind != JsonValueKind.Object)
        {
            return items;
        }
        foreach (var tool in tools.EnumerateObject())
        {
            var present = tool.Value.TryGetProperty("present", out var p)
                          && p.ValueKind == JsonValueKind.True;
            var detail = present
                ? tool.Value.TryGetProperty("version", out var v)
                  && v.ValueKind == JsonValueKind.String
                    ? $"version {v.GetString()}" : null
                : "Reinstalling the application should restore this.";
            items.Add(new SetupItem(FriendlyName(tool.Name), present, detail));
        }
        return items;
    }

    private static string FriendlyName(string tool) => tool switch
    {
        "ffmpeg" => "Video tools (FFmpeg)",
        "exiftool" => "Photo tools (ExifTool)",
        _ => tool,
    };
}
