using System;
using System.Diagnostics;
using System.IO;

namespace DjiEmbed.Gui.Services;

/// <summary>Opens the OS file manager with a file highlighted (Windows)
/// or its folder shown (elsewhere).</summary>
public static class Reveal
{
    public static void InFolder(string path)
    {
        if (For(path) is { } psi)
        {
            Process.Start(psi);
        }
    }

    /// <summary>
    /// The launch a reveal would make, or null when the path has no
    /// containing directory. Pure so tests can assert the exact
    /// invocation without spawning file managers.
    /// </summary>
    internal static ProcessStartInfo? For(string path)
    {
        var full = Path.GetFullPath(path);
        if (OperatingSystem.IsWindows())
        {
            return new ProcessStartInfo("explorer.exe", SelectArgument(full))
            { UseShellExecute = false };
        }
        return Path.GetDirectoryName(full) is { } dir
            ? new ProcessStartInfo(dir) { UseShellExecute = true }
            : null;
    }

    /// <summary>explorer.exe's highlight-this-file argument; the quotes
    /// keep paths with spaces intact.</summary>
    internal static string SelectArgument(string fullPath) =>
        $"/select,\"{fullPath}\"";
}
