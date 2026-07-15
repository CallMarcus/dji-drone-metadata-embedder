using System.Linq;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class MakeMapView : UserControl
{
    public MakeMapView()
    {
        InitializeComponent();
        AddHandler(DragDrop.DragOverEvent, OnDragOver);
        AddHandler(DragDrop.DropEvent, OnDrop);
    }

    private async void OnChooseFolderClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is not MakeMapViewModel vm
            || TopLevel.GetTopLevel(this) is not { } top)
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
            await vm.StartCommand.ExecuteAsync(path);
        }
    }

    private void OnDragOver(object? sender, DragEventArgs e)
    {
        e.DragEffects = e.DataTransfer.Contains(DataFormat.File)
            ? DragDropEffects.Copy
            : DragDropEffects.None;
    }

    private async void OnDrop(object? sender, DragEventArgs e)
    {
        if (DataContext is not MakeMapViewModel vm)
        {
            return;
        }
        var folder = e.DataTransfer.TryGetFiles()
            ?.Select(f => f.TryGetLocalPath())
            .FirstOrDefault(p => p is not null && System.IO.Directory.Exists(p));
        if (folder is not null)
        {
            await vm.StartCommand.ExecuteAsync(folder);
        }
    }
}
