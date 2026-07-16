using Avalonia.Controls;
using Avalonia.Interactivity;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class EmbedTelemetryView : UserControl
{
    public EmbedTelemetryView()
    {
        InitializeComponent();
        FolderPicking.EnableDrop(this, StartAsync, DropZone);
    }

    private async void OnChooseFolderClick(object? sender, RoutedEventArgs e) =>
        await FolderPicking.ChooseAsync(this, StartAsync);

    private System.Threading.Tasks.Task StartAsync(string folder) =>
        DataContext is EmbedTelemetryViewModel vm
            ? vm.StartCommand.ExecuteAsync(folder)
            : System.Threading.Tasks.Task.CompletedTask;
}
