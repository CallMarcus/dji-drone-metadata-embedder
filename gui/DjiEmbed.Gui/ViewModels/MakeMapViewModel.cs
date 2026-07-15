using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

public enum MakeMapStep
{
    Pick,
    Running,
    Done,
    Failed,
}

/// <summary>
/// The "Make a map" flow: folder in → progress → one result screen. Runs
/// flightmap and/or photomap (decided by <see cref="FolderInspector"/>)
/// through the bundled CLI and collects the map files it names.
/// </summary>
public partial class MakeMapViewModel(
    string? cliPath, DjiEmbedRunner runner, Action goHome) : ViewModelBase
{
    [ObservableProperty]
    public partial MakeMapStep Step { get; set; } = MakeMapStep.Pick;

    [ObservableProperty]
    public partial string StatusText { get; set; } = "";

    [ObservableProperty]
    public partial string? CurrentItem { get; set; }

    [ObservableProperty]
    public partial int Current { get; set; }

    [ObservableProperty]
    public partial int? Total { get; set; }

    [ObservableProperty]
    public partial string? ErrorMessage { get; set; }

    [ObservableProperty]
    public partial string? ErrorDetails { get; set; }

    public ObservableCollection<string> Outputs { get; } = [];

    private CancellationTokenSource? _cts;

    [RelayCommand]
    private async Task StartAsync(string folder)
    {
        if (cliPath is null)
        {
            Fail("The dji-embed engine could not be found next to this app. "
                 + "Reinstalling the application should fix this.");
            return;
        }

        var contents = FolderInspector.Inspect(folder);
        if (contents is { HasFlightLogs: false, HasPhotos: false })
        {
            Fail("No drone flight logs (.SRT) or photos were found in that "
                 + "folder. Pick the folder that contains your footage — "
                 + "subfolders are included automatically.");
            return;
        }

        Outputs.Clear();
        Step = MakeMapStep.Running;
        _cts = new CancellationTokenSource();
        try
        {
            if (contents.HasFlightLogs
                && !await RunOneAsync("flightmap", "Mapping your flights…", folder))
            {
                return;
            }
            if (contents.HasPhotos
                && !await RunOneAsync("photomap", "Mapping your photos…", folder))
            {
                return;
            }
            Step = MakeMapStep.Done;
        }
        catch (OperationCanceledException)
        {
            Step = MakeMapStep.Pick;
        }
        catch (Exception e)
        {
            Fail("Something went wrong while making the map.", e.Message);
        }
        finally
        {
            _cts.Dispose();
            _cts = null;
        }
    }

    private async Task<bool> RunOneAsync(string command, string status, string folder)
    {
        StatusText = status;
        CurrentItem = null;
        Current = 0;
        Total = null;

        var result = await runner.RunAsync(
            cliPath!, [command, folder, "-r"],
            new DirectProgress<ProgressEvent>(OnEvent), _cts!.Token);

        if (!result.Success)
        {
            Fail(result.Terminal?.Message
                 ?? "Something went wrong while making the map.",
                string.IsNullOrWhiteSpace(result.StderrText)
                    ? null : result.StderrText);
            return false;
        }
        foreach (var output in result.Terminal!.Outputs ?? [])
        {
            Outputs.Add(output);
        }
        return true;
    }

    private void OnEvent(ProgressEvent e)
    {
        if (e.Kind == ProgressEventKind.Progress)
        {
            Current = e.Current ?? 0;
            Total = e.Total;
            CurrentItem = e.Item;
        }
    }

    private void Fail(string message, string? details = null)
    {
        ErrorMessage = message;
        ErrorDetails = details;
        Step = MakeMapStep.Failed;
    }

    [RelayCommand]
    private void Cancel() => _cts?.Cancel();

    [RelayCommand]
    private void OpenOutput(string path) =>
        Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });

    [RelayCommand]
    private void GoHome() => goHome();

    /// <summary>
    /// Reports inline on the runner's read loop. Started from the UI
    /// thread, the runner's awaits hop back via the Avalonia sync context,
    /// so property updates land on the UI thread without a dispatcher.
    /// </summary>
    private sealed class DirectProgress<T>(Action<T> action) : IProgress<T>
    {
        public void Report(T value) => action(value);
    }
}
