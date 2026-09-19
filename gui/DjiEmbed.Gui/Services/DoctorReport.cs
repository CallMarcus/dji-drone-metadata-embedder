using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace DjiEmbed.Gui.Services;

/// <summary>One row of the setup checklist.</summary>
public sealed record SetupItem(string Label, bool Present, string? Detail);

/// <summary>Turns the doctor result summary into a novice-worded checklist.</summary>
public static class DoctorReport
{
    /// <param name="platform">The OS the advice is for; defaults to the
    /// running one. A seam for tests, like the other platform-branched
    /// services.</param>
    public static IReadOnlyList<SetupItem> Parse(
        JsonElement? summary, OSPlatform? platform = null)
    {
        var os = platform ?? Platforms.Current;
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
                : MissingAdvice(tool.Name, os);
            items.Add(new SetupItem(FriendlyName(tool.Name), present, detail));
        }
        return items;
    }

    /// <summary>The Windows installer bundles FFmpeg and ExifTool, so a
    /// reinstall restores them; the macOS app relies on Homebrew, and
    /// telling a Mac user to reinstall would send them nowhere (#572).
    /// Homebrew is only named for the two tools this app actually knows a
    /// formula for — a future tool key the CLI might report gets the
    /// generic package-manager advice instead of an invented brew
    /// command.</summary>
    private static string MissingAdvice(string tool, OSPlatform os) =>
        os == OSPlatform.Windows
            ? "Reinstalling the application should restore this."
        : os == OSPlatform.OSX && (tool == "ffmpeg" || tool == "exiftool")
            ? $"Install it with Homebrew: brew install {tool}"
        : "Install it with your package manager.";

    private static string FriendlyName(string tool) => tool switch
    {
        "ffmpeg" => "Video tools (FFmpeg)",
        "exiftool" => "Photo tools (ExifTool)",
        _ => tool,
    };
}
