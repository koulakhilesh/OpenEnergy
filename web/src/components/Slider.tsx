export function Slider(props: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit: string;
  help?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="field">
      <label>
        <span className="field-label">
          {props.label} <output>{props.unit}</output>
        </span>
        <input
          type="range"
          min={props.min}
          max={props.max}
          step={props.step ?? 1}
          value={props.value}
          onChange={(e) => props.onChange(Number(e.target.value))}
        />
      </label>
      {props.help && <p className="help">{props.help}</p>}
    </div>
  );
}
