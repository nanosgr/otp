import Button from './Button';

interface ModalFooterProps {
  onCancel: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  isEditing: boolean;
}

export default function ModalFooter({ onCancel, onSubmit, isSubmitting, isEditing }: ModalFooterProps) {
  return (
    <>
      <Button variant="secondary" onClick={onCancel}>Cancelar</Button>
      <Button onClick={onSubmit} disabled={isSubmitting}>
        {isSubmitting ? 'Guardando...' : isEditing ? 'Actualizar' : 'Crear'}
      </Button>
    </>
  );
}
