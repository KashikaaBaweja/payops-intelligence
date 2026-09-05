import { evaluatePassword, passwordStrength } from "../../lib/passwordPolicy";

export function PasswordRules({ password }: { password: string }) {
  const rules = evaluatePassword(password);
  const score = passwordStrength(password);
  return (
    <div className="password-meter">
      <div className="password-meter-bar" aria-hidden>
        <span style={{ width: `${(score / rules.length) * 100}%` }} />
      </div>
      <ul className="password-rules">
        {rules.map((rule) => (
          <li key={rule.code} className={rule.ok ? "ok" : ""}>
            {rule.ok ? "✓" : "○"} {rule.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
