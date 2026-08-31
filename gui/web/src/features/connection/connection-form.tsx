import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, PlugZap } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "../../components/ui/button";
import { cn } from "../../lib/utils";

const connectionSchema = z.object({
  host: z.string().trim().min(1, "Host is required").max(255),
  port: z.number().int().min(1, "Port must be at least 1").max(65535, "Port cannot exceed 65535"),
  service_name: z.string().trim().min(1, "Service name is required").max(128),
  username: z.string().trim().min(1, "Username is required").max(128),
  password: z.string().min(1, "Password is required").max(1024),
});

export type ConnectionFormValues = z.infer<typeof connectionSchema>;

type ConnectionFormProps = {
  connected: boolean;
  errorMessage: string | null;
  isSubmitting: boolean;
  onSubmit: (values: ConnectionFormValues) => Promise<boolean>;
};

const fieldClass =
  "h-9 w-full border border-border bg-background px-3 text-sm text-text outline-none transition-colors placeholder:text-text-muted/60 focus:border-focus focus:ring-1 focus:ring-focus disabled:opacity-60";

export function ConnectionForm({
  connected,
  errorMessage,
  isSubmitting,
  onSubmit,
}: ConnectionFormProps) {
  const [passwordVisible, setPasswordVisible] = useState(false);
  const {
    register,
    handleSubmit,
    resetField,
    formState: { errors },
  } = useForm<ConnectionFormValues>({
    resolver: zodResolver(connectionSchema),
    defaultValues: { host: "", port: 1521, service_name: "", username: "", password: "" },
  });

  const submit = handleSubmit(async (values) => {
    const successful = await onSubmit(values);
    if (successful) {
      resetField("password", { defaultValue: "" });
      setPasswordVisible(false);
    }
  });

  return (
    <form className="space-y-4" noValidate onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-[1fr_7rem]">
        <Field label="Host" error={errors.host?.message} htmlFor="oracle-host">
          <input
            {...register("host")}
            autoComplete="off"
            className={fieldClass}
            disabled={isSubmitting}
            id="oracle-host"
            placeholder="db.internal.example"
          />
        </Field>
        <Field label="Port" error={errors.port?.message} htmlFor="oracle-port">
          <input
            {...register("port", { valueAsNumber: true })}
            className={fieldClass}
            disabled={isSubmitting}
            id="oracle-port"
            inputMode="numeric"
            max={65535}
            min={1}
            type="number"
          />
        </Field>
      </div>

      <Field label="Service name" error={errors.service_name?.message} htmlFor="oracle-service">
        <input
          {...register("service_name")}
          autoComplete="off"
          className={fieldClass}
          disabled={isSubmitting}
          id="oracle-service"
          placeholder="ORCLPDB1"
        />
      </Field>

      <Field label="Username" error={errors.username?.message} htmlFor="oracle-username">
        <input
          {...register("username")}
          autoCapitalize="none"
          autoComplete="username"
          className={fieldClass}
          disabled={isSubmitting}
          id="oracle-username"
          spellCheck={false}
        />
      </Field>

      <Field label="Password" error={errors.password?.message} htmlFor="oracle-password">
        <div className="relative">
          <input
            {...register("password")}
            autoComplete="current-password"
            className={cn(fieldClass, "pr-10")}
            disabled={isSubmitting}
            id="oracle-password"
            type={passwordVisible ? "text" : "password"}
          />
          <button
            aria-label={passwordVisible ? "Hide password" : "Show password"}
            className="absolute inset-y-0 right-0 grid w-9 place-items-center text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
            onClick={() => setPasswordVisible((value) => !value)}
            type="button"
          >
            {passwordVisible ? (
              <EyeOff aria-hidden="true" className="size-4" />
            ) : (
              <Eye aria-hidden="true" className="size-4" />
            )}
          </button>
        </div>
      </Field>

      {errorMessage ? (
        <div
          className="border-l-2 border-danger bg-danger/8 px-3 py-2 text-sm text-danger"
          role="alert"
        >
          {errorMessage}
        </div>
      ) : null}

      <Button disabled={isSubmitting} type="submit">
        <PlugZap aria-hidden="true" className="size-4" />
        {isSubmitting
          ? "Testing connection…"
          : connected
            ? "Replace connection"
            : "Test connection"}
      </Button>
    </form>
  );
}

type FieldProps = {
  children: React.ReactNode;
  error?: string;
  htmlFor: string;
  label: string;
};

function Field({ children, error, htmlFor, label }: FieldProps) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-text" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? <p className="mt-1 text-xs text-danger">{error}</p> : null}
    </div>
  );
}
