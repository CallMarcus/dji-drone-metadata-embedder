using Avalonia.Controls;
using Avalonia.Interactivity;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class MakeMapView : UserControl
{
    public MakeMapView()
    {
        InitializeComponent();
        FolderPicking.EnableDrop(this, StartAsync, DropZone);
    }

    private async void OnChooseFolderClick(object? sender, RoutedEventArgs e) =>
        await FolderPicking.ChooseAsync(this, StartAsync);

    private System.Threading.Tasks.Task StartAsync(string folder) =>
        DataContext is MakeMapViewModel vm
            ? vm.StartCommand.ExecuteAsync(folder)
            : System.Threading.Tasks.Task.CompletedTask;
}
