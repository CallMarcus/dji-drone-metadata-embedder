using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace DjiEmbed.Gui.Services;

/// <summary>Opens the OS file manager with the file highlighted
/// (Windows Explorer, macOS Finder) or its folder shown (elsewhere).</summary>
public static class Reveal
{
    public static void InFolder(string path)
    {
        if (For(path, Platforms.Current) is { } psi)
        {
            Process.Start(psi);
        }
    }

    /// <summary>
    /// The launch a reveal would make, or null when the path has no
    /// containing directory. Pure so tests can assert every platform's
    /// exact invocation without spawning file managers.
    /// </summary>
    internal static ProcessStartInfo? For(string path, OSPlatform platform)
    {
        var full = Path.GetFullPath(path);
        if (platform == OSPlatform.Windows)
        {
            return new ProcessStartInfo("explorer.exe", SelectArgument(full))
            { UseShellExecute = false };
        }
        if (platform == OSPlatform.OSX)
        {
            // Finder's reveal: open -R highlights the file itself.
            var open = new ProcessStartInfo("open") { UseShellExecute = false };
            open.ArgumentList.Add("-R");
            open.ArgumentList.Add(full);
            return open;
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
