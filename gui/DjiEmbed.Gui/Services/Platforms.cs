using System;
using System.Runtime.InteropServices;

namespace DjiEmbed.Gui.Services;

/// <summary>The running OS as an OSPlatform value — the shared seam the
/// platform-branched services (WebViewSupport, TerminalLauncher, Reveal)
/// default to, so tests can call their overloads with any platform.</summary>
internal static class Platforms
{
    internal static OSPlatform Current =>
        OperatingSystem.IsWindows() ? OSPlatform.Windows
        : OperatingSystem.IsMacOS() ? OSPlatform.OSX
        : OSPlatform.Linux;
}
