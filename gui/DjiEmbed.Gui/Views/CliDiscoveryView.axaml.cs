using Avalonia.Controls;
using Avalonia.Interactivity;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class CliDiscoveryView : UserControl
{
    public CliDiscoveryView()
    {
        InitializeComponent();
    }

    private void OnCopyCommandClick(object? sender, RoutedEventArgs e)
    {
        if (sender is Button { DataContext: StarterCommand c } button)
        {
            _ = ClipboardCopy.CopyAsync(button, c.Command);
        }
    }
}
