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

    public MainViewModel()
    {
        CurrentPage = new HomeViewModel(StartTask);
    }

    public void StartTask(TaskKind kind)
    {
        CurrentPage = kind switch
        {
            TaskKind.MakeMap => new MakeMapViewModel(
                CliLocator.Find(), new DjiEmbedRunner(), GoHome),
            // Embed and check flows arrive in stage 3d.
            _ => CurrentPage,
        };
    }

    private void GoHome() => CurrentPage = new HomeViewModel(StartTask);
}
