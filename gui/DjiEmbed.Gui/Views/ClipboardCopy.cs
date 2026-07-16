using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Input.Platform;

namespace DjiEmbed.Gui.Views;

/// <summary>Puts text on the clipboard from any control in a window.</summary>
internal static class ClipboardCopy
{
    internal static Task CopyAsync(Control anchor, string? text) =>
        text is not null
        && TopLevel.GetTopLevel(anchor)?.Clipboard is { } clipboard
            ? clipboard.SetTextAsync(text)
            : Task.CompletedTask;
}
