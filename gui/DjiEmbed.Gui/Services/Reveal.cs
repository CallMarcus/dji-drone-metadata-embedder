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
        var full = Path.GetFullPath(path);
        if (OperatingSystem.IsWindows())
        {
            Process.Start(new ProcessStartInfo("explorer.exe",
                $"/select,\"{full}\"")
            { UseShellExecute = false });
            return;
        }
        if (Path.GetDirectoryName(full) is { } dir)
        {
            Process.Start(new ProcessStartInfo(dir) { UseShellExecute = true });
        }
    }
}
