using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui;

public partial class App : Application
{
    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            // The one persisted GUI state (workspace spec): MRU folders +
            // window bounds in %APPDATA%/DjiEmbed/state.json.
            var store = new GuiStateStore(GuiState.DefaultPath);
            desktop.MainWindow = new MainWindow(store)
            {
                DataContext = new MainViewModel(store),
            };
        }

        base.OnFrameworkInitializationCompleted();
    }
}