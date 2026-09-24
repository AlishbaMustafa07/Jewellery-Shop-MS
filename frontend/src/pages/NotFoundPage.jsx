import { Link } from "react-router-dom";

export default function NotFoundPage({ message = "This page does not exist." }) {
  return (
    <div className="card">
      <div className="empty">
        <h2>Not available</h2>
        <p>{message}</p>
        <Link to="/">Back to dashboard</Link>
      </div>
    </div>
  );
}
