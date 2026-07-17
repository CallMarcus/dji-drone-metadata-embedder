using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

public enum FlowStep
{
    Pick,
    Running,
    Done,
    Failed,
}

/// <summary>
/// Shared machinery for the task flows: one linear Pick → Running →
/// Done/Failed shape, live progress from the CLI event stream, and the
/// novice-first failure copy. Subclasses provide the actual commands.
/// </summary>
public abstract partial class FlowViewModel(
    string? cliPath, DjiEmbedRunner runner, Action goHome) : ViewModelBase
{
    [ObservableProperty]
    public partial FlowStep Step { get; set; } = FlowStep.Pick;

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

    public ObservableCollection<string> Warnings { get; } = [];

    /// <summary>The Running screen's one-liner: "file (n of total)".</summary>
    public string? ProgressDetail =>
        CurrentItem is null ? null
        : Total is { } total ? $"{CurrentItem} ({Current} of {total})"
        : CurrentItem;

    private const int DetailTailLines = 15;

    /// <summary>
    /// Failure details cut to the last lines for on-screen display;
    /// "Copy details" always gets the full text.
    /// </summary>
    public string? ErrorDetailsTail
    {
        get
        {
            if (ErrorDetails is null)
            {
                return null;
            }
            var lines = ErrorDetails.Split('\n');
            return lines.Length <= DetailTailLines
                ? ErrorDetails
                : "… (earlier output omitted — Copy details includes everything)\n"
                  + string.Join('\n', lines[^DetailTailLines..]);
        }
    }

    partial void OnErrorDetailsChanged(string? value) =>
        OnPropertyChanged(nameof(ErrorDetailsTail));

    partial void OnCurrentItemChanged(string? value) =>
        OnPropertyChanged(nameof(ProgressDetail));

    partial void OnCurrentChanged(int value) =>
        OnPropertyChanged(nameof(ProgressDetail));

    partial void OnTotalChanged(int? value) =>
        OnPropertyChanged(nameof(ProgressDetail));

    private CancellationTokenSource? _cts;

    /// <summary>The bundled CLI path, for subclasses that spawn beyond
    /// <see cref="RunCliAsync"/> (null when the CLI is missing).</summary>
    protected string? CliPath => cliPath;

    /// <summary>Fails fast when the bundled CLI is missing.</summary>
    protected bool EnsureCli()
    {
        if (cliPath is not null)
        {
            return true;
        }
        Fail("The dji-embed engine could not be found next to this app. "
             + "Reinstalling the application should fix this.");
        return false;
    }

    /// <summary>
    /// Runs <paramref name="body"/> with the shared Running/Done/Failed
    /// bookkeeping; cancel returns to Pick.
    /// </summary>
    protected async Task ExecuteFlowAsync(Func<Task<bool>> body)
    {
        Outputs.Clear();
        Warnings.Clear();
        Step = FlowStep.Running;
        _cts = new CancellationTokenSource();
        try
        {
            if (await body())
            {
                Step = FlowStep.Done;
            }
        }
        catch (OperationCanceledException)
        {
            Step = FlowStep.Pick;
        }
        catch (Exception e)
        {
            Fail(GenericFailureMessage, e.Message);
        }
        finally
        {
            _cts.Dispose();
            _cts = null;
        }
    }

    protected abstract string GenericFailureMessage { get; }

    /// <summary>Runs one CLI command, streaming progress into the flow.</summary>
    protected Task<CliRunResult> RunCliAsync(
        string status, IReadOnlyList<string> args)
    {
        StatusText = status;
        CurrentItem = null;
        Current = 0;
        Total = null;
        return runner.RunAsync(cliPath!, args,
            new DirectProgress<ProgressEvent>(OnEvent), _cts!.Token);
    }

    /// <summary>
    /// Runs one CLI command and requires contract success, collecting the
    /// outputs it names; failure fills the error state.
    /// </summary>
    protected async Task<bool> RunStepAsync(
        string status, IReadOnlyList<string> args)
    {
        var result = await RunCliAsync(status, args);
        if (!result.Success)
        {
            Fail(result.Terminal?.Message ?? GenericFailureMessage,
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
        else if (e.Kind == ProgressEventKind.Warning
                 && (e.Message ?? e.Item) is { } text)
        {
            Warnings.Add(e.Item is null || e.Message is null
                ? text : $"{e.Item}: {e.Message}");
        }
    }

    protected void Fail(string message, string? details = null)
    {
        ErrorMessage = message;
        ErrorDetails = details;
        Step = FlowStep.Failed;
    }

    [RelayCommand]
    private void Cancel() => _cts?.Cancel();

    [RelayCommand]
    private Task OpenOutput(string path) => OpenOutputCoreAsync(path);

    /// <summary>Opens one Done-screen output; subclasses may redirect.</summary>
    protected virtual Task OpenOutputCoreAsync(string path)
    {
        Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        return Task.CompletedTask;
    }

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
