using System;
using System.Collections.Generic;
using System.IO;

namespace DjiEmbed.Gui.Services;

/// <summary>A map an earlier run already left in the chosen folder.</summary>
public sealed record ExistingMap(
    string Path, string Title, DateTime WrittenUtc, bool Stale);

/// <summary>
/// Finds maps a previous run left in the chosen folder. The GUI never passes
/// <c>-o</c> by default, so the CLI's defaults apply and the two paths are
/// deterministic: <c>flightmap.html</c> and <c>photomap.html</c>, written
/// directly in the mapped folder. A map redirected elsewhere by the Flight
/// map "Save map to" override is deliberately out of scope (#328 spec) —
/// finding those would need a persisted record of past outputs.
/// </summary>
public static class ExistingMapFinder
{
    public static IReadOnlyList<ExistingMap> Find(
        string directory, FolderContents contents)
    {
        var found = new List<ExistingMap>();
        if (Probe(directory, "flightmap.html", "Flight map",
                contents.NewestFlightLogUtc) is { } flight)
        {
            found.Add(flight);
        }
        if (Probe(directory, "photomap.html", "Photo map",
                contents.NewestPhotoUtc) is { } photo)
        {
            found.Add(photo);
        }
        return found;
    }

    private static ExistingMap? Probe(string directory, string fileName,
        string title, DateTime? newestSourceUtc)
    {
        // One metadata snapshot: FileInfo.Exists caches the stat that
        // LastWriteTimeUtc then reads, so a file deleted mid-scan can't
        // surface as a phantom row stamped 1601.
        var file = new FileInfo(Path.Combine(directory, fileName));
        if (!file.Exists)
        {
            return null;
        }
        // A null source time (no footage of this kind) lifts to false: a map
        // nothing could have outrun is not stale.
        var written = file.LastWriteTimeUtc;
        return new ExistingMap(file.FullName, title, written,
            newestSourceUtc > written);
    }
}
