import MessageList from './MessageList';
import ControlBar from './ControlBar';
import ProgressBar from './ProgressBar';

function ChatFlow() {
  return (
    <div className="flex flex-col h-full">
      <MessageList />
      <ProgressBar />
      <ControlBar />
    </div>
  );
}

export default ChatFlow;
