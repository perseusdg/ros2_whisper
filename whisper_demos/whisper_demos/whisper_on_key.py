import sys

import rclpy
from builtin_interfaces.msg import Duration
from pynput.keyboard import Key, Listener
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.task import Future
from whisper_msgs.action._inference import Inference_FeedbackMessage
from std_msgs import String

from whisper_msgs.action import Inference


class WhisperOnKey(Node):
    def __init__(self, node_name: str) -> None:
        super().__init__(node_name=node_name)

        # whisper
        self.batch_idx = -1
        self.whisper_client = ActionClient(self, Inference, "/whisper/inference")

        while not self.whisper_client.wait_for_server(1):
            self.get_logger().warn(
                f"Waiting for {self.whisper_client._action_name} action server.."
            )
        self.get_logger().info(
            f"Action server {self.whisper_client._action_name} found."
        )

        self.key_listener = Listener(on_press=self.on_key)
        self.key_listener.start()
        self.whisper_publiser = self.create_publisher(String,'/whisper/inference_result',5)

        self.get_logger().info(self.info_string())

    def on_key(self, key: Key) -> None:
        if key == Key.esc:
            self.key_listener.stop()
            rclpy.shutdown()
            return

        if key == Key.space:
            # inference goal
            self.on_space()
            return

    def on_space(self) -> None:
        goal_msg = Inference.Goal()
        goal_msg.max_duration = Duration(sec=10, nanosec=0)
        self.get_logger().info(
            f"Requesting inference for {goal_msg.max_duration.sec} seconds..."
        )
        future = self.whisper_client.send_goal_async(
            goal_msg, feedback_callback=self.on_feedback
        )
        future.add_done_callback(self.on_goal_accepted)

    def on_goal_accepted(self, future: Future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected.")
            return

        self.get_logger().info("Goal accepted.")

        future = goal_handle.get_result_async()
        future.add_done_callback(self.on_done)

    def on_done(self, future: Future) -> None:
        self.get_logger().info("Goal Done is being processed.")
        result: Inference.Result = future.result().result
        msg = String()
        msg.data = result
        self.whisper_publiser.publish(msg)
        self.get_logger().info(f"Result: {result.transcriptions}")

    def on_feedback(self, feedback_msg: Inference_FeedbackMessage) -> None:
        if self.batch_idx != feedback_msg.feedback.batch_idx:
            print("")
            self.batch_idx = feedback_msg.feedback.batch_idx
        sys.stdout.write("\033[K")
        print(f"{feedback_msg.feedback.transcription}")
        sys.stdout.write("\033[F")

    def info_string(self) -> str:
        return (
            "\n\n"
            "\tStarting demo.\n"
            "\tPress ESC to exit.\n"
            "\tPress space to start listening.\n"
            "\tPress space again to stop listening.\n"
        )


def main(args=None):
    rclpy.init(args=args)
    whisper_on_key = WhisperOnKey(node_name="whisper_on_key")
    rclpy.spin(whisper_on_key)
