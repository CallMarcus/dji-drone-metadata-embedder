using CommunityToolkit.Mvvm.ComponentModel;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Window shell: swaps the current page. Every task is one linear flow
/// that ends back at the home screen.
/// </summary>
public partial class MainViewModel : ViewModelBase
{
    [ObservableProperty]
    public partial ViewModelBase CurrentPage { get; set; }

    // App-lifetime map server pool: revisiting "Make a map" reuses running
    // servers. No dispose hook needed — each server child exits when its
    // stdin pipe closes, i.e. when this process ends (MapServer docs).
    private readonly MapServer _mapServer = new();

    public MainViewModel()
    {
        CurrentPage = new HomeViewModel(StartTask);
    }

    public void StartTask(TaskKind kind)
    {
        CurrentPage = kind switch
        {
            TaskKind.MakeMap => new MakeMapViewModel(
                CliLocator.Find(), new DjiEmbedRunner(), _mapServer, GoHome),
            TaskKind.EmbedTelemetry => new EmbedTelemetryViewModel(
                CliLocator.Find(), new DjiEmbedRunner(), GoHome),
            TaskKind.CheckSetup => new CheckSetupViewModel(
                CliLocator.Find(), new DjiEmbedRunner(), GoHome),
            _ => CurrentPage,
        };
    }

    private void GoHome() => CurrentPage = new HomeViewModel(StartTask);
}
