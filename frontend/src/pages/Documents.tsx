import { useRef, useState, type ChangeEvent } from 'react';
import { FileText, Loader2, RefreshCcw, Trash2, Upload } from 'lucide-react';
import { isApiError } from '@/api/errors';
import {
  documentsService,
  type DocumentDeleteResponse,
  type DocumentsListResponse,
  type DocumentUploadResponse,
} from '@/services/api';
import { useQuery } from '@/hooks/useQuery';

type StatusMessage =
  | { type: 'success'; text: string }
  | { type: 'error'; text: string }
  | null;

function StatusBanner({ message }: { message: StatusMessage }) {
  if (!message) return null;

  const tone =
    message.type === 'success'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
      : 'border-rose-200 bg-rose-50 text-rose-800';

  return (
    <div className={['rounded-2xl border px-4 py-3 text-sm', tone].join(' ')}>
      {message.text}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-3xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center shadow-sm">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-sm">
        <FileText className="h-5 w-5 text-gray-500" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-gray-900">No uploaded documents yet</h3>
      <p className="mt-2 text-sm leading-6 text-gray-600">
        Upload a supported document to add it to the retrieval store. It will appear here after
        ingestion completes.
      </p>
    </div>
  );
}

function buildUploadMessage(response: DocumentUploadResponse) {
  return `${response.filename} uploaded successfully. ${response.chunk_count} chunk${
    response.chunk_count === 1 ? '' : 's'
  } indexed across ${response.page_count} page${response.page_count === 1 ? '' : 's'}.`;
}

function buildDeleteMessage(response: DocumentDeleteResponse) {
  return `${response.filename} deleted successfully. Removed ${response.chunks_deleted} chunk${
    response.chunks_deleted === 1 ? '' : 's'
  }.`;
}

function getDocumentErrorMessage(error: unknown, action: 'load' | 'upload' | 'delete') {
  if (isApiError(error) && error.httpStatus && error.httpStatus >= 500) {
    if (action === 'load') {
      return 'The document service is currently unavailable. Try refreshing again after the backend is ready.';
    }

    if (action === 'upload') {
      return 'The document could not be uploaded because the document service returned a server error.';
    }

    return 'The document could not be deleted because the document service returned a server error.';
  }

  if (error instanceof Error) return error.message;

  if (action === 'load') return 'Failed to load documents.';
  if (action === 'upload') return 'Failed to upload document.';
  return 'Failed to delete document.';
}

export default function Documents() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [statusMessage, setStatusMessage] = useState<StatusMessage>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingFilename, setDeletingFilename] = useState<string | null>(null);

  const {
    data,
    isLoading,
    refetch,
  } = useQuery<DocumentsListResponse>(() => documentsService.list(), [], {
    onError: (queryError) => {
      setStatusMessage({ type: 'error', text: getDocumentErrorMessage(queryError, 'load') });
    },
  });

  const documents = data?.documents ?? [];

  const handleRefresh = async () => {
    setStatusMessage(null);
    refetch();
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) return;

    setIsUploading(true);
    setStatusMessage(null);

    try {
      const response = await documentsService.upload(file);
      setStatusMessage({ type: 'success', text: buildUploadMessage(response) });
      refetch();
    } catch (uploadError) {
      setStatusMessage({ type: 'error', text: getDocumentErrorMessage(uploadError, 'upload') });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (filename: string) => {
    setDeletingFilename(filename);
    setStatusMessage(null);

    try {
      const response = await documentsService.delete(filename);
      setStatusMessage({ type: 'success', text: buildDeleteMessage(response) });
      refetch();
    } catch (deleteError) {
      setStatusMessage({ type: 'error', text: getDocumentErrorMessage(deleteError, 'delete') });
    } finally {
      setDeletingFilename(null);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      <div className="flex-1 overflow-auto px-6 py-6 lg:px-8">
        <div className="mx-auto max-w-6xl space-y-6">
          <div className="rounded-3xl border border-gray-200 bg-white p-8 shadow-sm">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary-700">
                  Documents
                </p>
                <h2 className="mt-3 text-3xl font-semibold text-gray-900">
                  Document management
                </h2>
                <p className="mt-3 max-w-3xl text-base leading-7 text-gray-600">
                  Upload, review, refresh, and delete the source documents currently available to
                  the retrieval pipeline.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={handleUploadClick}
                  disabled={isUploading}
                  className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  {isUploading ? 'Uploading...' : 'Upload document'}
                </button>

                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={isLoading}
                  className="inline-flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCcw className={['h-4 w-4', isLoading ? 'animate-spin' : ''].join(' ')} />
                  Refresh
                </button>
              </div>
            </div>
          </div>

          <StatusBanner message={statusMessage} />

          <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Uploaded documents</h3>
                <p className="mt-1 text-sm text-gray-600">
                  Current files stored in the document retrieval collection.
                </p>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-2 text-sm text-gray-700">
                Total: {data?.total ?? 0}
              </div>
            </div>

            <div className="mt-6">
              {isLoading ? (
                <div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4 text-sm text-gray-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading document list...
                </div>
              ) : statusMessage?.type === 'error' && documents.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center shadow-sm">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-sm">
                    <FileText className="h-5 w-5 text-gray-500" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold text-gray-900">
                    Document service unavailable
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-gray-600">
                    The page is working, but the backend document route returned an error. Use
                    refresh once the service is available again.
                  </p>
                </div>
              ) : documents.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="space-y-3">
                  {documents.map((filename) => {
                    const isDeleting = deletingFilename === filename;

                    return (
                      <div
                        key={filename}
                        className="flex flex-col gap-4 rounded-2xl border border-gray-200 p-4 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-3">
                            <div className="rounded-2xl bg-slate-100 p-2">
                              <FileText className="h-4 w-4 text-slate-700" />
                            </div>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium text-gray-900">
                                {filename}
                              </div>
                              <div className="mt-1 text-xs text-gray-500">
                                Available for retrieval and grounding.
                              </div>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleDelete(filename)}
                          disabled={isDeleting}
                          className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm font-medium text-rose-700 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {isDeleting ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                          {isDeleting ? 'Deleting...' : 'Delete'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
