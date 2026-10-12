#include "OtherworldMacFullScreen.h"

#include "CoreMinimal.h"

#if PLATFORM_MAC
#include "Mac/MacSystemIncludes.h"
#include "Mac/CocoaThread.h"
#include "Misc/CoreDelegates.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldFullScreen, Log, All);

// A borderless full-screen game on the Mac (EWindowMode::WindowedFullscreen) is a macOS
// full-screen Space. There the Dock and the menu bar are only auto-hidden and the hot
// corners stay live: all of them answer a pointer at the edge of the screen, which a
// shown cursor reaches (the engine's cursor lock clamps the pointer after the push, it
// does not prevent it). So while the game is in front its display is captured, which is
// what the engine's exclusive Fullscreen does, less the change of display mode: macOS
// keeps its Dock, menu bar and hot corners off a captured display, and only a window
// above the capture's shield is seen there. The capture is given back whenever another
// app comes forward or the window leaves full screen, and for as long as Command is
// down: a captured display takes Command-Tab away, and would hide the switcher.
// The window's own title bar is the one thing the capture leaves: in a full-screen Space
// AppKit keeps it in a window of its own, above the screen, and slides it down with the
// menu bar. That window is emptied (the engine cannot make the Mac's game window
// borderless: PLATFORM_SUPPORTS_BORDERLESS_WINDOW is 0 there).
// What did not work, in the order tried (12 Oct 2026):
// - Exclusive Fullscreen, the engine's own way: it cannot take a native size on many
//   monitors (Scripts/graphics_menu/CLAUDE.md, "Full screen on the Mac").
// - Replacing FCocoaWindow's window:willUseFullScreenPresentationOptions: it is never
//   called, the window being in full screen before this module starts.
// - [NSApp setPresentationOptions:] with HideDock | HideMenuBar: macOS takes it (1029
//   becomes 1034) and the Dock comes up all the same.
// - Raising the window to NSStatusWindowLevel (25) with no capture: the menu bar still
//   drops over it and a hot corner still fires.
static CGDirectDisplayID CapturedDisplay = kCGNullDirectDisplay;
static NSWindow* ShieldedWindow = nil;

static void ReleaseDisplay()
{
	if (CapturedDisplay == kCGNullDirectDisplay)
	{
		return;
	}
	if (ShieldedWindow && [[NSApp windows] containsObject:ShieldedWindow])
	{
		[ShieldedWindow setLevel:NSNormalWindowLevel];
	}
	ShieldedWindow = nil;
	CGDisplayRelease(CapturedDisplay);
	UE_LOG(LogOtherworldFullScreen, Log, TEXT("display %u released"), (uint32)CapturedDisplay);
	CapturedDisplay = kCGNullDirectDisplay;
}

// In full screen the title bar's buttons are not in the game's window: the window they
// are in is the bar AppKit slides down. Nothing of it is drawn and it takes no clicks.
static void EmptyTitleBar(NSWindow* FullScreenWindow)
{
	NSWindow* Bar = [[FullScreenWindow standardWindowButton:NSWindowCloseButton] window];
	if (!Bar || Bar == FullScreenWindow)
	{
		return;
	}
	NSView* Root = [Bar contentView];
	while ([Root superview])
	{
		Root = [Root superview];
	}
	if (Root && ![Root isHidden])
	{
		[Root setHidden:YES];
		[Bar setIgnoresMouseEvents:YES];
		UE_LOG(LogOtherworldFullScreen, Log, TEXT("full-screen title bar emptied (%s)"), *FString(NSStringFromClass([Bar class])));
	}
}

static void UpdateDisplayCapture()
{
	NSWindow* FullScreenWindow = nil;
	const bool bCommandDown = ([NSEvent modifierFlags] & NSEventModifierFlagCommand) != 0;
	if ([NSApp isActive] && !bCommandDown)
	{
		Class GameWindow = NSClassFromString(@"FCocoaWindow");
		for (NSWindow* Window in [NSApp windows])
		{
			if ([Window isKindOfClass:GameWindow] && ([Window styleMask] & NSWindowStyleMaskFullScreen) != 0 && [Window screen])
			{
				FullScreenWindow = Window;
				break;
			}
		}
	}
	if (!FullScreenWindow)
	{
		ReleaseDisplay();
		return;
	}

	const CGDirectDisplayID Display = [[[[FullScreenWindow screen] deviceDescription] objectForKey:@"NSScreenNumber"] unsignedIntValue];
	if (CapturedDisplay != Display)
	{
		ReleaseDisplay();
		// A window over the shield already is the engine's exclusive Fullscreen, which
		// holds its own capture: left alone.
		if ([FullScreenWindow level] > CGShieldingWindowLevel())
		{
			return;
		}
		const CGError Result = CGDisplayCapture(Display);
		if (Result != kCGErrorSuccess)
		{
			UE_LOG(LogOtherworldFullScreen, Warning, TEXT("display %u not captured: error %d"), (uint32)Display, (int32)Result);
			return;
		}
		CapturedDisplay = Display;
		UE_LOG(LogOtherworldFullScreen, Log, TEXT("display %u captured: no Dock, menu bar or hot corners"), (uint32)Display);
	}
	EmptyTitleBar(FullScreenWindow);
	// Each time: the engine puts the levels it saved back when the app comes forward.
	ShieldedWindow = FullScreenWindow;
	if ([FullScreenWindow level] <= CGShieldingWindowLevel())
	{
		[FullScreenWindow setLevel:CGShieldingWindowLevel() + 1];
	}
}
#endif

void OtherworldMacFullScreen::HideDockAndMenuBar()
{
#if PLATFORM_MAC
	// The editor's windows stay where they are: its Dock is wanted.
	if (GIsEditor || IsRunningCommandlet() || IsRunningDedicatedServer())
	{
		return;
	}
	// Events, nothing polled: into full screen, out of it, the game coming forward and
	// another app taking its place (a captured display shows nothing of that app).
	for (NSString* Event in @[NSWindowDidEnterFullScreenNotification, NSWindowDidExitFullScreenNotification,
	                          NSWindowDidBecomeKeyNotification, NSWindowDidChangeScreenNotification,
	                          NSApplicationDidBecomeActiveNotification, NSApplicationDidResignActiveNotification])
	{
		[[NSNotificationCenter defaultCenter] addObserverForName:Event object:nil queue:nil
		                                              usingBlock:^(NSNotification*) { UpdateDisplayCapture(); }];
	}
	[[NSNotificationCenter defaultCenter] addObserverForName:NSApplicationWillResignActiveNotification object:nil queue:nil
	                                              usingBlock:^(NSNotification*) { ReleaseDisplay(); }];
	// Command down or up: the capture is not held while it is down.
	[NSEvent addLocalMonitorForEventsMatchingMask:NSEventMaskFlagsChanged handler:^NSEvent*(NSEvent* Event)
	{
		UpdateDisplayCapture();
		return Event;
	}];
	// And the launch, which none of those reports: the window is in full screen already.
	MainThreadCall(^{ UpdateDisplayCapture(); }, false);
	FCoreDelegates::GetOnPostEngineInit().AddLambda([] { MainThreadCall(^{ UpdateDisplayCapture(); }, false); });
#endif
}
