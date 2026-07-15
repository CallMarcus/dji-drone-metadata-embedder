using System;
using System.IO;
using System.Runtime.InteropServices;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Finds the dji-embed CLI executable. Search order: the
/// <c>DJIEMBED_CLI</c> environment override (dev/test), then beside the GUI
/// executable and in its <c>cli/</c> subfolder (the installer layouts),
/// then PATH (a pip/winget install).
/// </summary>
public static class CliLocator
{
    public const string EnvVar = "DJIEMBED_CLI";

    private static string ExeName =>
        RuntimeInformation.IsOSPlatform(OSPlatform.Windows)
            ? "dji-embed.exe" : "dji-embed";

    public static string? Find() => Find(
        Environment.GetEnvironmentVariable(EnvVar),
        AppContext.BaseDirectory,
        Environment.GetEnvironmentVariable("PATH"));

    public static string? Find(
        string? envOverride, string baseDirectory, string? pathVariable)
    {
        if (!string.IsNullOrEmpty(envOverride) && File.Exists(envOverride))
        {
            return envOverride;
        }

        foreach (var candidate in new[]
                 {
                     Path.Combine(baseDirectory, ExeName),
                     Path.Combine(baseDirectory, "cli", ExeName),
                 })
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        foreach (var dir in (pathVariable ?? "").Split(
                     Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            var candidate = Path.Combine(dir, ExeName);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }
}
