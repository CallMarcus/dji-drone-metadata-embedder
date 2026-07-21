using System;
using System.Collections.Generic;
using System.Linq;

namespace DjiEmbed.Gui.ViewModels;

public enum WorkspaceModeKind
{
    FlightMap,
    PhotoMap,
    Embed,
    Convert,
    Setup,
}

/// <summary>What the SOURCE area may hold for a mode (GUI 2.0 spec, M4a):
/// a folder, a single telemetry file, or nothing (Setup).</summary>
[Flags]
public enum SourceKinds
{
    None = 0,
    Folder = 1,
    File = 2,
}

/// <summary>
/// One entry in the workspace mode strip (GUI 2.0 spec). M1 ships four;
/// Convert and Verify join in M4.
/// </summary>
public sealed record WorkspaceMode(
    WorkspaceModeKind Kind,
    string Title,
    string Verb,
    SourceKinds Sources,
    string FailureMessage)
{
    public static readonly IReadOnlyList<WorkspaceMode> All =
    [
        new(WorkspaceModeKind.FlightMap, "Flight map", "Generate flight map",
            Sources: SourceKinds.Folder,
            "Something went wrong while mapping your flights."),
        new(WorkspaceModeKind.PhotoMap, "Photo map", "Generate photo map",
            Sources: SourceKinds.Folder,
            "Something went wrong while mapping your photos."),
        new(WorkspaceModeKind.Embed, "Embed telemetry", "Embed telemetry",
            Sources: SourceKinds.Folder,
            "Something went wrong while embedding the flight data."),
        new(WorkspaceModeKind.Setup, "Setup", "Check my setup",
            Sources: SourceKinds.None,
            "The setup check could not be completed."),
    ];

    public static WorkspaceMode Of(WorkspaceModeKind kind) =>
        All.First(m => m.Kind == kind);
}
