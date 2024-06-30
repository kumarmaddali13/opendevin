import { Tooltip } from "@nextui-org/react";
import React, { useEffect } from "react";
import ArrowIcon from "#/assets/arrow";
import PauseIcon from "#/assets/pause";
import PlayIcon from "#/assets/play";
import store from "#/store";
import AgentState from "#/types/AgentState";
import { clearMessages } from "#/state/chatSlice";
import { useAgentState } from "#/hooks/useAgentState";

const IgnoreTaskStateMap: { [k: string]: AgentState[] } = {
  [AgentState.PAUSED]: [
    AgentState.INIT,
    AgentState.PAUSED,
    AgentState.STOPPED,
    AgentState.FINISHED,
    AgentState.REJECTED,
    AgentState.AWAITING_USER_INPUT,
  ],
  [AgentState.RUNNING]: [
    AgentState.INIT,
    AgentState.RUNNING,
    AgentState.STOPPED,
    AgentState.FINISHED,
    AgentState.REJECTED,
    AgentState.AWAITING_USER_INPUT,
  ],
  [AgentState.STOPPED]: [AgentState.INIT, AgentState.STOPPED],
};

interface ButtonProps {
  isDisabled: boolean;
  content: string;
  action: AgentState;
  handleAction: (action: AgentState) => void;
  large?: boolean;
}

function ActionButton({
  isDisabled = false,
  content,
  action,
  handleAction,
  children,
  large = false,
}: React.PropsWithChildren<ButtonProps>): React.ReactNode {
  return (
    <Tooltip content={content} closeDelay={100}>
      <button
        onClick={() => handleAction(action)}
        disabled={isDisabled}
        className={`
         relative overflow-visible cursor-default hover:cursor-pointer group
          disabled:cursor-not-allowed disabled:opacity-60
          ${large ? "rounded-full bg-bg-light p-3" : "rounded-full bg-bg-light p-2"}
          transition-all duration-300 ease-in-out
          border border-primary/40 hover:border-primary/60
          shadow-md hover:shadow-lg
        `}
        type="button"
      >
        <span className="relative z-10 group-hover:filter group-hover:drop-shadow-[0_0_5px_rgba(255,64,0,0.4)]">
          {children}
        </span>
      </button>
    </Tooltip>
  );
}

function AgentControlBar() {
  const { curAgentState, setAgentState } = useAgentState();
  const [desiredState, setDesiredState] = React.useState(AgentState.INIT);
  const [isLoading, setIsLoading] = React.useState(false);

  const handleAction = (action: AgentState) => {
    if (IgnoreTaskStateMap[action].includes(curAgentState)) {
      return;
    }

    if (action === AgentState.STOPPED) {
      store.dispatch(clearMessages());
    } else {
      setIsLoading(true);
    }

    setDesiredState(action);
    setAgentState(action);
  };

  useEffect(() => {
    if (curAgentState === desiredState) {
      if (curAgentState === AgentState.STOPPED) {
        store.dispatch(clearMessages());
      }
      setIsLoading(false);
    } else if (curAgentState === AgentState.RUNNING) {
      setDesiredState(AgentState.RUNNING);
    }
    // We only want to run this effect when curAgentState changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [curAgentState]);

  return (
    <div className="flex items-center gap-3">
      {curAgentState === AgentState.PAUSED ? (
        <ActionButton
          isDisabled={
            isLoading ||
            IgnoreTaskStateMap[AgentState.RUNNING].includes(curAgentState)
          }
          content="Resume the agent task"
          action={AgentState.RUNNING}
          handleAction={handleAction}
          large
        >
          <PlayIcon />
        </ActionButton>
      ) : (
        <ActionButton
          isDisabled={
            isLoading ||
            IgnoreTaskStateMap[AgentState.PAUSED].includes(curAgentState)
          }
          content="Pause the current task"
          action={AgentState.PAUSED}
          handleAction={handleAction}
          large
        >
          <PauseIcon />
        </ActionButton>
      )}
      <ActionButton
        isDisabled={isLoading}
        content="Start a new task"
        action={AgentState.STOPPED}
        handleAction={handleAction}
      >
        <ArrowIcon />
      </ActionButton>
    </div>
  );
}

export default AgentControlBar;
