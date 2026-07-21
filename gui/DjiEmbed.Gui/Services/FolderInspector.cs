using System;
using System.IO;

namespace DjiEmbed.Gui.Services;

public sealed record FolderContents(
    bool HasFlightLogs, bool HasPhotos, bool HasVideos,
    bool HasTopLevelFlightLogs, bool HasTopLevelPhotos, bool HasTopLevelVideos,
    DateTime? NewestFlightLogUtc, DateTime? NewestPhotoUtc);

/// <summary>
/// Decides which commands apply to a dropped folder. Extension-only and
/// recursive, mirroring the CLI dragdrop semantics: the CLI itself is the
/// authority on whether files actually contain telemetry/GPS.
/// Also records the newest write time per media kind, which is what tells
/// an existing map it has been outrun by new footage (#328). Videos get no
/// timestamp because they produce no map.
/// </summary>
public static class FolderInspector
{
    public static FolderContents Inspect(string directory)
    {
        var hasVideos = false;
        DateTime? newestFlightLog = null;
        DateTime? newestPhoto = null;
        // Per-kind top-level presence: embed reads one directory level and
        // the map commands recurse only with -r, so the pre-flight guards
        // need "is it where this command will look", not just "is it
        // anywhere" (#333, #338). The walk echoes the directory argument as
        // each file's prefix, so a plain string compare against the
        // trimmed root is exact.
        var root = Path.TrimEndingDirectorySeparator(directory);
        var topFlightLogs = false;
        var topPhotos = false;
        var topVideos = false;
        // No early exit: the newest write time is only known once every
        // file has been seen. IgnoreInaccessible keeps an unreadable
        // subfolder from throwing out of the (async void) folder pick.
        foreach (var file in Directory.EnumerateFiles(directory, "*",
                     new EnumerationOptions
                     {
                         RecurseSubdirectories = true,
                         IgnoreInaccessible = true,
                         // The SearchOption overload this replaces skipped
                         // nothing by attribute; EnumerationOptions would
                         // default to skipping Hidden and System files.
                         AttributesToSkip = FileAttributes.None,
                     }))
        {
            var ext = Path.GetExtension(file);
            var topLevel = string.Equals(
                Path.GetDirectoryName(file), root,
                StringComparison.OrdinalIgnoreCase);
            if (ext.Equals(".srt", StringComparison.OrdinalIgnoreCase))
            {
                newestFlightLog = Newer(newestFlightLog, File.GetLastWriteTimeUtc(file));
                topFlightLogs |= topLevel;
            }
            else if (ext.Equals(".jpg", StringComparison.OrdinalIgnoreCase)
                     || ext.Equals(".jpeg", StringComparison.OrdinalIgnoreCase)
                     || ext.Equals(".dng", StringComparison.OrdinalIgnoreCase))
            {
                newestPhoto = Newer(newestPhoto, File.GetLastWriteTimeUtc(file));
                topPhotos |= topLevel;
            }
            else if (ext.Equals(".mp4", StringComparison.OrdinalIgnoreCase)
                     || ext.Equals(".mov", StringComparison.OrdinalIgnoreCase))
            {
                hasVideos = true;
                topVideos |= topLevel;
            }
        }
        return new FolderContents(
            newestFlightLog is not null, newestPhoto is not null, hasVideos,
            topFlightLogs, topPhotos, topVideos,
            newestFlightLog, newestPhoto);
    }

    private static DateTime Newer(DateTime? running, DateTime candidate) =>
        running is { } previous && previous >= candidate ? previous : candidate;
}
