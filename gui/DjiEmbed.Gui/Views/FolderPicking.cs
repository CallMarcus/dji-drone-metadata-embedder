using System;
using System.Collections.Generic;
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
    /// <summary>
    /// Pick a directory, or <c>null</c> when the picker was dismissed.
    /// Also serves as a command-output destination picker: Embed's
    /// <c>-o</c> is a directory, not a file, so its Choose… button routes
    /// here rather than to <see cref="PickSaveAsync"/>'s save dialog.
    /// </summary>
    internal static async Task<string?> PickFolderAsync(
        Control anchor, string title, string? startFolder = null)
    {
        if (TopLevel.GetTopLevel(anchor) is not { } top)
        {
            return null;
        }
        // Best-effort: an unreachable start folder means the picker's
        // own default, nothing more.
        var start = startFolder is null
            ? null
            : await top.StorageProvider.TryGetFolderFromPathAsync(startFolder);
        var folders = await top.StorageProvider.OpenFolderPickerAsync(
            new FolderPickerOpenOptions
            {
                AllowMultiple = false,
                Title = title,
                SuggestedStartLocation = start,
            });
        return folders.FirstOrDefault()?.TryGetLocalPath();
    }

    internal static async Task ChooseAsync(
        Control anchor, Func<string, Task> onFolder,
        string? startFolder = null)
    {
        if (await PickFolderAsync(
                anchor, "Choose the folder with your footage", startFolder)
            is { } path)
        {
            await onFolder(path);
        }
    }

    /// <summary>Extensions the SOURCE area accepts as a single file (M4a):
    /// the telemetry sources <c>convert</c> reads.</summary>
    private static readonly string[] SourceFileExtensions =
        [".srt", ".mp4", ".mov"];

    /// <summary>Pure drop-payload resolution: the first directory wins,
    /// otherwise the first telemetry file; anything else yields nothing.</summary>
    internal static void ResolveDrop(
        IEnumerable<string> paths, out string? folder, out string? file)
    {
        folder = null;
        file = null;
        foreach (var path in paths)
        {
            if (System.IO.Directory.Exists(path))
            {
                folder = path;
                return;
            }
            if (file is null
                && System.IO.File.Exists(path)
                && Array.Exists(SourceFileExtensions, e => path.EndsWith(
                    e, StringComparison.OrdinalIgnoreCase)))
            {
                file = path;
            }
        }
    }

    internal static void EnableDrop(
        Control target, Func<string, Task> onFolder, Control? dropZone = null,
        Func<string, Task>? onFile = null)
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
            var paths = e.DataTransfer.TryGetFiles()
                ?.Select(f => f.TryGetLocalPath())
                .Where(p => p is not null)
                .Select(p => p!) ?? [];
            ResolveDrop(paths, out var folder, out var file);
            if (folder is not null)
            {
                await onFolder(folder);
            }
            else if (file is not null && onFile is not null)
            {
                await onFile(file);
            }
        });
    }

    /// <summary>Toggles the "dragover" style class on the drop zone.</summary>
    internal static void SetDragOver(Control zone, bool active) =>
        zone.Classes.Set("dragover", active);

    /// <summary>Pick where to save a map's HTML, or <c>null</c> when the
    /// dialog was dismissed.</summary>
    internal static Task<string?> PickSaveAsync(
        Control anchor, string title, string suggestedName) =>
        PickSaveAsync(anchor, title, suggestedName, "Web map", "*.html");

    /// <summary>Pick where to save a file of the given kind, or <c>null</c>
    /// when the dialog was dismissed — the typed form behind
    /// <see cref="PickSaveAsync(Control, string, string)"/>, used directly
    /// by Convert (M4a) so each format gets its own extension and filter
    /// label instead of "Web map"/"*.html".</summary>
    internal static async Task<string?> PickSaveAsync(
        Control anchor, string title, string suggestedName,
        string filterLabel, string pattern)
    {
        if (TopLevel.GetTopLevel(anchor) is not { } top)
        {
            return null;
        }
        var file = await top.StorageProvider.SaveFilePickerAsync(
            new FilePickerSaveOptions
            {
                Title = title,
                SuggestedFileName = suggestedName,
                DefaultExtension = pattern[(pattern.LastIndexOf('.') + 1)..],
                FileTypeChoices =
                [
                    new FilePickerFileType(filterLabel) { Patterns = [pattern] },
                ],
            });
        return file?.TryGetLocalPath();
    }

    /// <summary>Pick a single telemetry file, or <c>null</c> when dismissed.</summary>
    internal static async Task<string?> PickSourceFileAsync(Control anchor)
    {
        if (TopLevel.GetTopLevel(anchor) is not { } top)
        {
            return null;
        }
        var files = await top.StorageProvider.OpenFilePickerAsync(
            new FilePickerOpenOptions
            {
                AllowMultiple = false,
                Title = "Choose a flight log or drone video",
                FileTypeFilter =
                [
                    new FilePickerFileType("Telemetry sources")
                    {
                        Patterns = ["*.srt", "*.SRT", "*.mp4", "*.MP4",
                                    "*.mov", "*.MOV"],
                    },
                ],
            });
        return files.FirstOrDefault()?.TryGetLocalPath();
    }
}
