#include "OtherworldNetLibrary.h"

#include "Components/ActorComponent.h"
#include "Engine/NetDriver.h"
#include "GameFramework/Actor.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(OtherworldNetLibrary)

bool UOtherworldNetLibrary::IsLevelActor(const AActor* Actor)
{
	return Actor != nullptr && Actor->IsNetStartupActor();
}

bool UOtherworldNetLibrary::SendServerEvent(UObject* Target, FName Event, const TArray<FString>& Arguments)
{
	UFunction* Function = Target ? Target->FindFunction(Event) : nullptr;
	const UActorComponent* Component = Cast<UActorComponent>(Target);
	const AActor* Actor = Component ? Component->GetOwner() : Cast<AActor>(Target);
	if (!Function || !Function->HasAnyFunctionFlags(FUNC_NetServer) || !Actor || Actor->HasAuthority())
	{
		UE_LOG(LogNet, Warning, TEXT("SendServerEvent: %s of %s is not a Server event that travels from here (%s)"),
		       *Event.ToString(), *GetNameSafe(Target),
		       !Function ? TEXT("no such function") : !Function->HasAnyFunctionFlags(FUNC_NetServer)
		       ? TEXT("not a Server event") : TEXT("it would run here"));
		return false;
	}
	TArray<uint8> Storage;
	Storage.SetNumZeroed(FMath::Max<int32>(Function->ParmsSize, 1));
	uint8* Parms = Storage.GetData();
	int32 Index = 0;
	bool bRead = true;
	for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It, ++Index)
	{
		It->InitializeValue_InContainer(Parms);
		bRead = bRead && Arguments.IsValidIndex(Index)
			&& It->ImportText_Direct(*Arguments[Index], It->ContainerPtrToValuePtr<void>(Parms), nullptr, PPF_None);
	}
	bRead = bRead && Index == Arguments.Num();
	if (!bRead)
	{
		UE_LOG(LogNet, Warning, TEXT("SendServerEvent: %s takes %d parameter(s), and %d were given or one did not read"),
		       *Event.ToString(), Index, Arguments.Num());
	}
	const bool bSent = bRead && Target->CallRemoteFunction(Function, Parms, nullptr, nullptr);
	for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
	{
		It->DestroyValue_InContainer(Parms);
	}
	return bSent;
}
