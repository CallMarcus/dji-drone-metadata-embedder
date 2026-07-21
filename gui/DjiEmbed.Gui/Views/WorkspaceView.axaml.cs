using System;
using System.ComponentModel;
using System.IO;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class WorkspaceView : UserControl
{
    private WorkspaceViewModel? _vm;
    private NativeWebView? _webView;

    /// <summary>
    /// Whether this machine can host a NativeWebView at all — a test seam
    /// defaulting to the real probe. Must be decided before DataContext is
    /// assigned: setting it fires SyncPreview immediately, so tests set
    /// this first. See <see cref="AttachPreview"/> for why the gate, not
    /// the try/catch, is the real protection.
    /// </summary>
    internal Func<bool> WebViewGate { get; set; } =
        static () => WebViewSupport.IsLikelyAvailable;

    /// <summary>
    /// Save-file picking for the two map panels' Choose… buttons — a test
    /// seam (#335) defaulting to the real save dialog, which cannot open
    /// headless: (anchor, title, suggestedName) → the chosen path, or null
    /// when dismissed.
    /// </summary>
    internal Func<Control, string, string, Task<string?>> SavePicker
    { get; set; } = FolderPicking.PickSaveAsync;

    /// <summary>
    /// Folder picking for Embed's Choose… button (its <c>-o</c> is a
    /// directory, not a file) — the same seam shape as
    /// <see cref="SavePicker"/>: (anchor, title) → the chosen path, or
    /// null when dismissed.
    /// </summary>
    internal Func<Control, string, Task<string?>> OutputFolderPicker
    { get; set; } = FolderPicking.PickFolderAsync;

    /// <summary>
    /// Single-file picking for the source card's "Choose a file…"
    /// button — a test seam in the <see cref="SavePicker"/> mould:
    /// (anchor) → the chosen path, or null when dismissed.
    /// </summary>
    internal Func<Control, Task<string?>> FilePicker
    { get; set; } = FolderPicking.PickSourceFileAsync;

    /// <summary>Save-file picking for Convert's Choose… button — the
    /// <see cref="SavePicker"/> seam with the format's own extension:
    /// (anchor, title, suggestedName, filterLabel, pattern) → path or null.</summary>
    internal Func<Control, string, string, string, string, Task<string?>>
        ConvertSavePicker { get; set; } = FolderPicking.PickSaveAsync;

    public WorkspaceView()
    {
        InitializeComponent();
        FolderPicking.EnableDrop(this, SetFolderAsync, DropZone, SetFileAsync);
        DataContextChanged += (_, _) =>
        {
            if (_vm is not null)
            {
                _vm.PropertyChanged -= OnVmPropertyChanged;
            }
            _vm = DataContext as WorkspaceViewModel;
            if (_vm is not null)
            {
                _vm.PropertyChanged += OnVmPropertyChanged;
            }
            // The VM outlives the view (ViewLocator rebuilds it on every
            // page flip): adopt any preview that is already showing.
            SyncPreview();
        };
    }

    private void OnVmPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(WorkspaceViewModel.PreviewUrl))
        {
            SyncPreview();
        }
    }

    private void SyncPreview()
    {
        if (_vm?.PreviewUrl is { } url)
        {
            AttachPreview(url);
        }
        else
        {
            PreviewHost.Child = null;
        }
    }

    /// <summary>
    /// One WebView per view instance, created on first use — the view is
    /// rebuilt each time navigation returns here. A machine that gets
    /// this far but still has no usable engine (the spec's
    /// old-Windows-10 case) gets a calm note in the pane — the map is
    /// always one "Open in browser" click away, never an error dialog.
    /// </summary>
    private void AttachPreview(string url)
    {
        if (!WebViewGate())
        {
            // Never even construct the control here: adapter creation
            // happens on attach and its failures surface asynchronously
            // via the dispatcher (observed: the GTK adapter throwing on
            // display-less CI), where no try/catch of ours can reach
            // them. The gate is the real protection; the catch below
            // only covers synchronous construction failures.
            PreviewHost.Child = MakeFallbackNote();
            return;
        }
        try
        {
            _webView ??= new NativeWebView();
            PreviewHost.Child = _webView;
            _webView.Source = new Uri(url);
        }
        catch (Exception)
        {
            _webView = null;
            PreviewHost.Child = MakeFallbackNote();
        }
    }

    private static TextBlock MakeFallbackNote() => new()
    {
        Text = "The map is ready — use “Open in browser” above to "
               + "view it. (The inline preview isn't available on "
               + "this computer.)",
        TextWrapping = TextWrapping.Wrap,
        Opacity = 0.7,
        FontSize = 13,
        MaxWidth = 420,
        HorizontalAlignment = HorizontalAlignment.Center,
        VerticalAlignment = VerticalAlignment.Center,
    };

    private async void OnChooseFolderClick(object? sender, RoutedEventArgs e) =>
        await FolderPicking.ChooseAsync(this, SetFolderAsync);

    private async void OnChooseFileClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is WorkspaceViewModel vm
            && await FilePicker(this) is { } path)
        {
            vm.SetFile(path);
        }
    }

    private async void OnChooseOutputClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is WorkspaceViewModel vm
            && await SavePicker(this, "Save the flight map as", "flightmap.html")
                is { } path)
        {
            vm.FlightOptions.Output = path;
        }
    }

    private async void OnChoosePhotoOutputClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is WorkspaceViewModel vm
            && await SavePicker(this, "Save the photo map as", "photomap.html")
                is { } path)
        {
            vm.PhotoOptions.Output = path;
        }
    }

    private async void OnChooseEmbedOutputClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is WorkspaceViewModel vm
            && await OutputFolderPicker(
                this, "Choose where to save the embedded copies") is { } path)
        {
            vm.EmbedOptions.Output = path;
        }
    }

    private async void OnChooseConvertOutputClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is not WorkspaceViewModel vm
            || vm.SelectedFile is not { } file)
        {
            return;
        }
        var fmt = vm.ConvertOptions.SelectedFormat;
        var name = Path.GetFileNameWithoutExtension(file) + "." + fmt.Suffix;
        if (await ConvertSavePicker(this, "Save the converted file as", name,
                fmt.Label, "*." + fmt.Suffix) is { } path)
        {
            vm.ConvertOptions.Output = path;
        }
    }

    private async void OnCopyDetailsClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is FlowViewModel vm)
        {
            await ClipboardCopy.CopyAsync(this, vm.ErrorDetails);
        }
    }

    private async void OnCopyCommandClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is WorkspaceViewModel vm)
        {
            await ClipboardCopy.CopyAsync(this, vm.CommandPreview);
        }
    }

    private System.Threading.Tasks.Task SetFolderAsync(string folder) =>
        DataContext is WorkspaceViewModel vm
            ? vm.SetFolderAsync(folder)
            : System.Threading.Tasks.Task.CompletedTask;

    private Task SetFileAsync(string file)
    {
        (DataContext as WorkspaceViewModel)?.SetFile(file);
        return Task.CompletedTask;
    }
}
