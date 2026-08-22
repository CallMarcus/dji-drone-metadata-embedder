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
            // window bounds in DjiEmbed/state.json under the platform's
            // app-data folder — %APPDATA% on Windows, ~/Library/Application
            // Support on macOS (the .NET 8+ GetFolderPath mapping).
            var store = new GuiStateStore(GuiState.DefaultPath);
            var main = new MainViewModel(store);
            desktop.MainWindow = new MainWindow(store)
            {
                DataContext = main,
            };
            // Launch update note (#319): opt-in, once a day at most, never
            // blocking — fire-and-forget; it swallows its own failures.
            _ = main.StartUpdateCheckAsync();
        }

        base.OnFrameworkInitializationCompleted();
    }
}