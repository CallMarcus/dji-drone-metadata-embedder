using System;
using System.Collections.Generic;
using System.IO;

namespace DjiEmbed.Gui.Services;

public sealed record FolderContents(
    bool HasFlightLogs, bool HasPhotos, bool HasVideos,
    bool HasTopLevelFlightLogs, bool HasTopLevelPhotos, bool HasTopLevelVideos,
    DateTime? NewestFlightLogUtc, DateTime? NewestPhotoUtc,
    bool HasTelemetryVideos, bool HasTopLevelTelemetryVideos);

/// <summary>
/// Decides which commands apply to a dropped folder. Extension-only and
/// recursive, mirroring the CLI dragdrop semantics: the CLI itself is the
/// authority on whether files actually contain telemetry/GPS.
/// A <em>telemetry video</em> (#572) is an MP4/MOV with no .SRT of the
/// same stem in the same directory; the CLI's flightmap reads such
/// videos for the telemetry track inside them (Parrot Anafi, sidecar-less
/// DJI), so they count as flight sources. Whether one really carries
/// telemetry is again the CLI's call at run time.
/// Also records the newest write time per media kind, which is what tells
/// an existing map it has been outrun by new footage (#328). Paired videos
/// contribute no timestamp (their SRT carries it); telemetry videos do.
/// </summary>
public static class FolderInspector
{
    public static FolderContents Inspect(string directory)
    {
        var hasFlightLogs = false;
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
        // Pairing needs every SRT of a directory before its videos can be
        // classified, and the walk order is undefined, so videos are held
        // back and resolved after the single pass. Keys are
        // "<directory>|<stem>", compared case-insensitively: DJI_0001.MP4
        // beside dji_0001.srt is a pair. This is a deliberate divergence
        // from the CLI's own _sidecarless_videos
        // (src/dji_metadata_embedder/geo/flightmap.py), which compares
        // exact paths: this is a Windows-shaped heuristic (case-insensitive
        // filesystem), and the CLI remains the authority on what actually
        // gets read at run time.
        var srtStems = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var videos = new List<(string Path, string Key, bool TopLevel)>();
        // Embed never receives -o (CommandBuilder.cs), so its output always
        // lands at <root>/processed/<stem>_metadata.mp4 with no .SRT beside
        // it. Left uncorrected, every Embed run would make its own copies
        // look like fresh telemetry videos and mark every existing flight
        // map as outrun (#328) on the very next folder pick.
        var processedDir = Path.Combine(root, "processed");
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
                hasFlightLogs = true;
                newestFlightLog = Newer(newestFlightLog, File.GetLastWriteTimeUtc(file));
                topFlightLogs |= topLevel;
                srtStems.Add(StemKey(file));
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
                videos.Add((file, StemKey(file), topLevel));
            }
        }
        var hasTelemetryVideos = false;
        var topTelemetryVideos = false;
        foreach (var (path, key, topLevel) in videos)
        {
            if (srtStems.Contains(key))
            {
                continue;
            }
            if (string.Equals(Path.GetDirectoryName(path), processedDir,
                    StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            hasTelemetryVideos = true;
            topTelemetryVideos |= topLevel;
            newestFlightLog = Newer(newestFlightLog, File.GetLastWriteTimeUtc(path));
        }
        return new FolderContents(
            hasFlightLogs, newestPhoto is not null, hasVideos,
            topFlightLogs, topPhotos, topVideos,
            newestFlightLog, newestPhoto,
            hasTelemetryVideos, topTelemetryVideos);
    }

    // "|" cannot appear in a Windows path component, and the key is only
    // ever compared for equality (never parsed back apart), so it cannot
    // collide with a real directory-plus-stem combination.
    private static string StemKey(string file) =>
        Path.GetDirectoryName(file) + "|" + Path.GetFileNameWithoutExtension(file);

    private static DateTime Newer(DateTime? running, DateTime candidate) =>
        running is { } previous && previous >= candidate ? previous : candidate;
}
