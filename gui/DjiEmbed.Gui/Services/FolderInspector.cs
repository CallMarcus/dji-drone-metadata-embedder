using System;
using System.IO;

namespace DjiEmbed.Gui.Services;

public sealed record FolderContents(bool HasFlightLogs, bool HasPhotos);

/// <summary>
/// Decides which map commands apply to a dropped folder. Extension-only and
/// recursive, mirroring the CLI dragdrop semantics: the CLI itself is the
/// authority on whether files actually contain telemetry/GPS.
/// </summary>
public static class FolderInspector
{
    public static FolderContents Inspect(string directory)
    {
        var hasFlightLogs = false;
        var hasPhotos = false;
        foreach (var file in Directory.EnumerateFiles(
                     directory, "*", SearchOption.AllDirectories))
        {
            var ext = Path.GetExtension(file);
            if (ext.Equals(".srt", StringComparison.OrdinalIgnoreCase))
            {
                hasFlightLogs = true;
            }
            else if (ext.Equals(".jpg", StringComparison.OrdinalIgnoreCase)
                     || ext.Equals(".jpeg", StringComparison.OrdinalIgnoreCase)
                     || ext.Equals(".dng", StringComparison.OrdinalIgnoreCase))
            {
                hasPhotos = true;
            }
            if (hasFlightLogs && hasPhotos)
            {
                break;
            }
        }
        return new FolderContents(hasFlightLogs, hasPhotos);
    }
}
