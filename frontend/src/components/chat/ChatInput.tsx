import { Textarea } from "@nextui-org/react";
import React from "react";
import { useTranslation } from "react-i18next";
import { VscArrowUp } from "react-icons/vsc";
import { twMerge } from "tailwind-merge";
import { I18nKey } from "#/i18n/declaration";
import AgentTaskState from "#/types/AgentTaskState";

interface ChatInputProps {
  disabled?: boolean;
  onSendMessage: (message: string) => void;
  currentTaskState: AgentTaskState;
}

function ChatInput({
  disabled,
  onSendMessage,
  currentTaskState,
}: ChatInputProps) {
  const { t } = useTranslation();

  const [message, setMessage] = React.useState("");
  // This is true when the user is typing in an IME (e.g., Chinese, Japanese)
  const [isComposing, setIsComposing] = React.useState(false);

  const handleSendChatMessage = () => {
    if (message.trim()) {
      onSendMessage(message);
      setMessage("");
    }
  };
  const handleSendContinueMsg = () => {
    const continueMsg = t(I18nKey.CHAT_INTERFACE$INPUT_CONTINUE_MESSAGE);
    setMessage(continueMsg);
    onSendMessage(continueMsg);
  };

  const onKeyPress = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !isComposing) {
      event.preventDefault(); // prevent a new line
      if (!disabled) {
        handleSendChatMessage();
      }
    }
  };

  return (
    <>
      {currentTaskState === AgentTaskState.AWAITING_USER_INPUT && (
        <div className="mx-3 pt-3 text-center">
          <button
            type="button"
            className="w-full relative bg-transparent border rounded-lg p-1 border-white hover:opacity-80 cursor-pointer select-none bottom-[10px] transition active:bg-white active:text-black hover:bg-neutral-500"
            onClick={handleSendContinueMsg}
          >
            <span className="m-2">
              {`>>> ${t(I18nKey.CHAT_INTERFACE$INPUT_CONTINUE_MESSAGE)} `}
            </span>
          </button>
        </div>
      )}
      <div className="w-full relative text-base flex">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={onKeyPress}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder={t(I18nKey.CHAT_INTERFACE$INPUT_PLACEHOLDER)}
          className="pb-3 px-3"
          classNames={{
            inputWrapper: "bg-neutral-700 border border-neutral-600 rounded-lg",
            input: "pr-16 text-neutral-400",
          }}
          maxRows={10}
          minRows={1}
          variant="bordered"
        />

        <button
          type="button"
          onClick={handleSendChatMessage}
          disabled={disabled}
          className={twMerge(
            "bg-transparent border rounded-lg p-1 border-white hover:opacity-80 cursor-pointer select-none absolute right-5 bottom-[19px] transition active:bg-white active:text-black",
            disabled
              ? "cursor-not-allowed border-neutral-400 text-neutral-400"
              : "hover:bg-neutral-500 ",
          )}
          aria-label="Send message"
        >
          <VscArrowUp />
        </button>
      </div>
    </>
  );
}

ChatInput.defaultProps = {
  disabled: false,
};

export default ChatInput;
