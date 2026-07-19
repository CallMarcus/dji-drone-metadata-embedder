using System;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Whether the inline map preview is worth attempting on this machine.
/// The app ships for Windows, where WebView2 is preinstalled from
/// Windows 11 on; elsewhere (dev boxes, CI) the preview degrades to the
/// done-card and the browser, per the GUI 2.0 spec's degradation rule.
/// A machine that passes this probe but still lacks a usable engine is
/// caught by the try/catch around the control itself.
/// </summary>
public static class WebViewSupport
{
    public static bool IsLikelyAvailable => OperatingSystem.IsWindows();
}
