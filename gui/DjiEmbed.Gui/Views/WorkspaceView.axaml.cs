using System;
using System.ComponentModel;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

public partial class WorkspaceView : UserControl
{
    private WorkspaceViewModel? _vm;
    private NativeWebView? _webView;

    public WorkspaceView()
    {
        InitializeComponent();
        FolderPicking.EnableDrop(this, SetFolderAsync, DropZone);
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
        };
    }

    private void OnVmPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName != nameof(WorkspaceViewModel.PreviewUrl))
        {
            return;
        }
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
    /// One WebView for the window's lifetime, created on first use. A
    /// machine that gets this far but still has no usable engine (the
    /// spec's old-Windows-10 case) gets a calm note in the pane — the
    /// map is always one "Open in browser" click away, never an error
    /// dialog.
    /// </summary>
    private void AttachPreview(string url)
    {
        try
        {
            _webView ??= new NativeWebView();
            PreviewHost.Child = _webView;
            _webView.Source = new Uri(url);
        }
        catch (Exception)
        {
            _webView = null;
            PreviewHost.Child = new TextBlock
            {
                Text = "The map is ready — use “Open in browser” above to "
                       + "view it. (The inline preview isn't available on "
                       + "this computer.)",
                TextWrapping = TextWrapping.Wrap,
                Opacity = 0.7,
                MaxWidth = 420,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
            };
        }
    }

    private async void OnChooseFolderClick(object? sender, RoutedEventArgs e) =>
        await FolderPicking.ChooseAsync(this, SetFolderAsync);

    private async void OnCopyDetailsClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is FlowViewModel vm)
        {
            await ClipboardCopy.CopyAsync(this, vm.ErrorDetails);
        }
    }

    private System.Threading.Tasks.Task SetFolderAsync(string folder) =>
        DataContext is WorkspaceViewModel vm
            ? vm.SetFolderAsync(folder)
            : System.Threading.Tasks.Task.CompletedTask;
}
