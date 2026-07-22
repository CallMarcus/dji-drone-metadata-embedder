using System.Collections.Generic;
using System.Linq;
using Avalonia;
using Avalonia.Controls;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Views;

public partial class MainWindow : Window
{
    private readonly GuiStateStore? _store;

    // Last bounds seen in the Normal state: Avalonia has no RestoreBounds,
    // so closing while maximized saves these instead — un-maximizing after
    // the next launch then lands somewhere sane.
    private PixelPoint _normalPosition;
    private Size _normalSize;

    public MainWindow() : this(null)
    {
    }

    public MainWindow(GuiStateStore? store)
    {
        InitializeComponent();
        _store = store;
        if (store?.State.Window is { } b
            && GuiState.RestorableOn(b, ScreenRects()))
        {
            // CenterScreen (the XAML default) would override a manual
            // Position on open; switching to Manual makes ours stick.
            WindowStartupLocation = WindowStartupLocation.Manual;
            Position = new PixelPoint(b.X, b.Y);
            Width = b.Width;
            Height = b.Height;
            if (b.Maximized)
            {
                WindowState = WindowState.Maximized;
            }
        }
        _normalPosition = Position;
        _normalSize = new Size(Width, Height);
        // These subscriptions are never torn down — deliberately: this is
        // the app's only window and it lives for the process lifetime.
        PositionChanged += (_, e) =>
        {
            if (WindowState == WindowState.Normal)
            {
                _normalPosition = e.Point;
            }
        };
        SizeChanged += (_, e) =>
        {
            if (WindowState == WindowState.Normal)
            {
                _normalSize = e.NewSize;
            }
        };
        Closing += (_, _) => SaveBounds();
    }

    // Position is physical pixels while Width/Height are DIPs, so under a
    // non-100% scale this intersection is approximate — good enough for
    // "is any part of the window still reachable", which is all the gate
    // asks (spec 2026-07-22).
    private IReadOnlyList<(int X, int Y, int Width, int Height)> ScreenRects() =>
        Screens.All
            .Select(s => (s.WorkingArea.X, s.WorkingArea.Y,
                s.WorkingArea.Width, s.WorkingArea.Height))
            .ToList();

    private void SaveBounds()
    {
        if (_store is null)
        {
            return;
        }
        // Live values while Normal (robust even where the platform never
        // fired SizeChanged); the tracked normals only stand in while the
        // window is maximized and the live ones describe the wrong state.
        var maximized = WindowState == WindowState.Maximized;
        var pos = maximized ? _normalPosition : Position;
        var size = maximized ? _normalSize : new Size(Width, Height);
        _store.SaveWindow(new WindowBounds(
            pos.X, pos.Y, (int)size.Width, (int)size.Height, maximized));
    }
}
