using System;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Platform.Storage;

namespace DjiEmbed.Gui.Views;

/// <summary>
/// Shared pick-a-folder plumbing for the flow views: the system folder
/// picker and window drag-drop, both funnelling into one callback.
/// </summary>
internal static class FolderPicking
{
    private static async Task<string?> PickFolderAsync(Control anchor, string title)
    {
        if (TopLevel.GetTopLevel(anchor) is not { } top)
        {
            return null;
        }
        var folders = await top.StorageProvider.OpenFolderPickerAsync(
            new FolderPickerOpenOptions
            {
                AllowMultiple = false,
                Title = title,
            });
        return folders.FirstOrDefault()?.TryGetLocalPath();
    }

    internal static async Task ChooseAsync(
        Control anchor, Func<string, Task> onFolder)
    {
        if (await PickFolderAsync(anchor, "Choose the folder with your footage")
            is { } path)
        {
            await onFolder(path);
        }
    }

    /// <summary>
    /// Pick a destination directory for a command's output. Embed's
    /// <c>-o</c> is a directory, not a file, so it reuses the folder picker
    /// rather than <see cref="SaveMapAsync"/>'s save-file dialog.
    /// </summary>
    internal static async Task ChooseOutputFolderAsync(
        Control anchor, Action<string> onPath, string title)
    {
        if (await PickFolderAsync(anchor, title) is { } path)
        {
            onPath(path);
        }
    }

    internal static void EnableDrop(
        Control target, Func<string, Task> onFolder, Control? dropZone = null)
    {
        target.AddHandler(DragDrop.DragOverEvent, (_, e) =>
            e.DragEffects = e.DataTransfer.Contains(DataFormat.File)
                ? DragDropEffects.Copy
                : DragDropEffects.None);
        if (dropZone is not null)
        {
            target.AddHandler(DragDrop.DragEnterEvent, (_, e) =>
                SetDragOver(dropZone,
                    e.DataTransfer.Contains(DataFormat.File)));
            target.AddHandler(DragDrop.DragLeaveEvent, (_, _) =>
                SetDragOver(dropZone, false));
        }
        target.AddHandler(DragDrop.DropEvent, async (_, e) =>
        {
            if (dropZone is not null)
            {
                SetDragOver(dropZone, false);
            }
            var folder = e.DataTransfer.TryGetFiles()
                ?.Select(f => f.TryGetLocalPath())
                .FirstOrDefault(p =>
                    p is not null && System.IO.Directory.Exists(p));
            if (folder is not null)
            {
                await onFolder(folder);
            }
        });
    }

    /// <summary>Toggles the "dragover" style class on the drop zone.</summary>
    internal static void SetDragOver(Control zone, bool active) =>
        zone.Classes.Set("dragover", active);

    internal static async Task SaveMapAsync(
        Control anchor, Action<string> onPath, string title, string suggestedName)
    {
        if (TopLevel.GetTopLevel(anchor) is not { } top)
        {
            return;
        }
        var file = await top.StorageProvider.SaveFilePickerAsync(
            new FilePickerSaveOptions
            {
                Title = title,
                SuggestedFileName = suggestedName,
                DefaultExtension = "html",
                FileTypeChoices =
                [
                    new FilePickerFileType("Web map") { Patterns = ["*.html"] },
                ],
            });
        var path = file?.TryGetLocalPath();
        if (path is not null)
        {
            onPath(path);
        }
    }
}
