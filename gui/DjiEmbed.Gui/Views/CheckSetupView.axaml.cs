using Avalonia.Controls;
using Avalonia.Interactivity;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class CheckSetupView : UserControl
{
    public CheckSetupView()
    {
        InitializeComponent();
        // The checklist is the whole point of the screen: start the check
        // as soon as the view appears, no button to find.
        Loaded += OnLoaded;
    }

    private async void OnLoaded(object? sender, RoutedEventArgs e)
    {
        if (DataContext is CheckSetupViewModel { Step: FlowStep.Pick } vm)
        {
            await vm.StartCommand.ExecuteAsync(null);
        }
    }

    private async void OnCopyDetailsClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is FlowViewModel vm)
        {
            await ClipboardCopy.CopyAsync(this, vm.ErrorDetails);
        }
    }
}
