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
    internal static async Task ChooseAsync(
        Control anchor, Func<string, Task> onFolder)
    {
        if (TopLevel.GetTopLevel(anchor) is not { } top)
        {
            return;
        }
        var folders = await top.StorageProvider.OpenFolderPickerAsync(
            new FolderPickerOpenOptions
            {
                AllowMultiple = false,
                Title = "Choose the folder with your footage",
            });
        var path = folders.FirstOrDefault()?.TryGetLocalPath();
        if (path is not null)
        {
            await onFolder(path);
        }
    }

    internal static void EnableDrop(Control target, Func<string, Task> onFolder)
    {
        target.AddHandler(DragDrop.DragOverEvent, (_, e) =>
            e.DragEffects = e.DataTransfer.Contains(DataFormat.File)
                ? DragDropEffects.Copy
                : DragDropEffects.None);
        target.AddHandler(DragDrop.DropEvent, async (_, e) =>
        {
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
}
