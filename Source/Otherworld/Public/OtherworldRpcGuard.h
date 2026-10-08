// What a Server event checks before it does anything (task A5): how often
// this connection has asked, and whether the point it names is one its own
// view could rest on. A C++ RPC has the engine's _Validate hook for this and
// a Blueprint one has nothing, so every Server event on the player's weapon
// component calls Allow first, through one fragment (Scripts/net/guard.py),
// and Server_Fire calls AimAllowed behind it.
//
// Only a remote connection is counted. In single player, for a listen
// server's own player and for a character the server drives itself (a load
// test's bot), both checks pass and nothing is counted: the request did not
// come over a wire.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OtherworldRpcGuard.generated.h"

class UNetConnection;

UCLASS(ClassGroup = (Otherworld), meta = (BlueprintSpawnableComponent))
class OTHERWORLD_API UOtherworldRpcGuard : public UActorComponent
{
	GENERATED_BODY()

public:
	UOtherworldRpcGuard();

	/**
	 * May the Server event Name run now? A token bucket per event name per
	 * connection: Rates[Name] tokens a second (DefaultRate for a name with no
	 * row), BurstSeconds of them held at most. A refusal logs
	 * "RPC-REFUSED <Name>"; more than KickRefusals of them within KickSeconds
	 * closes the connection with ClosedByRpcGuard.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	bool Allow(FName Name);

	/**
	 * Could this player's view rest on AimPoint? The view is a cone along
	 * the way this machine's copy looks (GetBaseAimRotation), opening by
	 * AimConeDegrees from a disc AimSideCm wide that stands AimBackCm behind
	 * its eyes: the camera is behind and beside the character, so a near
	 * point is off the eyes' own line. Refused outside it, behind it, or
	 * further than AimMaxCm from the eyes. A refusal logs
	 * "RPC-REFUSED AimPoint".
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	bool AimAllowed(FVector AimPoint);

	// Tokens a second, by event name (Scripts/net/guard_consts.py writes them).
	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	TMap<FName, float> Rates;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float DefaultRate = 5.f;

	// How many seconds of its rate a bucket holds: what may arrive at once.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float BurstSeconds = 1.f;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	int32 KickRefusals = 100;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float KickSeconds = 10.f;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float AimConeDegrees = 20.f;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float AimBackCm = 300.f;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float AimSideCm = 150.f;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Net")
	float AimMaxCm = 105000.f;

	// For the probes: what this character's requests came to, on the server.
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Net")
	int32 Counted = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Net")
	int32 Refused = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Net")
	int32 AimRefused = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Net")
	bool bKicked = false;

private:
	/** The remote connection the owner's requests arrive on, or none. */
	UNetConnection* RemoteConnection() const;
};
