export interface FeedbackData {
  email: string;
  token: string;
  feedback: "positive" | "negative";
  permissions: "public" | "private";
  trajectory: unknown[];
}


export const sendFeedback = async (data: FeedbackData) =>
  fetch("/api/submit-feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: data.email,
      token: data.token,
      feedback: data.feedback,
      permissions: data.permissions,
      trajectory: data.trajectory,
    }),
  });
