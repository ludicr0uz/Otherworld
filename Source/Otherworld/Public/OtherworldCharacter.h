// The player character's native parent. It exists for one thing: a Character's
// movement component is a native subobject, so only a native class can choose
// its class. BP_ThirdPersonCharacter is reparented onto this by
// Scripts/combat/player_move.py; everything else about the player stays in
// the Blueprint the builders author.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "OtherworldCharacter.generated.h"

UCLASS()
class OTHERWORLD_API AOtherworldCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	explicit AOtherworldCharacter(const FObjectInitializer& ObjectInitializer);
};
