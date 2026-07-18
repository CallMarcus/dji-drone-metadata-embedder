using Avalonia.Controls;
using Avalonia.Interactivity;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class WorkspaceView : UserControl
{
    public WorkspaceView()
    {
        InitializeComponent();
        FolderPicking.EnableDrop(this, SetFolderAsync, DropZone);
    }

    private async void OnChooseFolderClick(object? sender, RoutedEventArgs e) =>
        await FolderPicking.ChooseAsync(this, SetFolderAsync);

    private async void OnCopyDetailsClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is FlowViewModel vm)
        {
            await ClipboardCopy.CopyAsync(this, vm.ErrorDetails);
        }
    }

    private System.Threading.Tasks.Task SetFolderAsync(string folder) =>
        DataContext is WorkspaceViewModel vm
            ? vm.SetFolderAsync(folder)
            : System.Threading.Tasks.Task.CompletedTask;
}
