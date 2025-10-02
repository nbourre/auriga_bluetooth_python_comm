using AurigaRobotControl.Core.Interfaces;
using AurigaRobotControl.Core.Models;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace AurigaRobotControl.Data.Services
{
    public class FileCommandSequenceService : ICommandSequenceService
    {
        private readonly string _sequencesDirectory;
        private readonly string _sequencesFilePath;
        private readonly List<CommandSequence> _sequences;
        private readonly object _lockObject = new();
        private CancellationTokenSource? _executionCancellationSource;
        private readonly IDataLoggingService _logger;

        public bool IsExecuting => _executionCancellationSource != null && !_executionCancellationSource.Token.IsCancellationRequested;

        public event EventHandler<CommandSequenceExecutionEventArgs>? SequenceExecutionStarted;
        public event EventHandler<CommandSequenceExecutionEventArgs>? SequenceExecutionCompleted;
        public event EventHandler<CommandSequenceExecutionEventArgs>? SequenceExecutionError;
        public event EventHandler<CommandSequenceStepEventArgs>? SequenceStepExecuted;

        public FileCommandSequenceService(IDataLoggingService logger)
        {
            _logger = logger;
            _sequencesDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "AurigaRobotControl", "Sequences");
            _sequencesFilePath = Path.Combine(_sequencesDirectory, "command_sequences.json");
            _sequences = new List<CommandSequence>();
            
            Directory.CreateDirectory(_sequencesDirectory);
            _ = LoadSequencesAsync();
        }

        public async Task<List<CommandSequence>> GetAllSequencesAsync()
        {
            await LoadSequencesAsync();
            
            lock (_lockObject)
            {
                return new List<CommandSequence>(_sequences);
            }
        }

        public async Task<CommandSequence?> GetSequenceByIdAsync(int id)
        {
            await LoadSequencesAsync();
            
            lock (_lockObject)
            {
                return _sequences.FirstOrDefault(s => s.Id == id);
            }
        }

        public async Task<int> SaveSequenceAsync(CommandSequence sequence)
        {
            await LoadSequencesAsync();
            
            lock (_lockObject)
            {
                if (sequence.Id == 0)
                {
                    // New sequence
                    sequence.Id = _sequences.Count > 0 ? _sequences.Max(s => s.Id) + 1 : 1;
                    sequence.CreatedAt = DateTime.Now;
                    _sequences.Add(sequence);
                }
                else
                {
                    // Update existing sequence
                    var existingIndex = _sequences.FindIndex(s => s.Id == sequence.Id);
                    if (existingIndex >= 0)
                    {
                        sequence.ModifiedAt = DateTime.Now;
                        _sequences[existingIndex] = sequence;
                    }
                    else
                    {
                        // ID provided but sequence doesn't exist, add as new
                        sequence.CreatedAt = DateTime.Now;
                        _sequences.Add(sequence);
                    }
                }
            }

            await SaveSequencesToFileAsync();
            await _logger.LogCommandAsync(new RobotCommand { Description = $"Command sequence '{sequence.Name}' saved with ID {sequence.Id}" }, true);
            
            return sequence.Id;
        }

        public async Task<bool> DeleteSequenceAsync(int id)
        {
            await LoadSequencesAsync();
            
            CommandSequence? deletedSequence = null;
            
            lock (_lockObject)
            {
                var index = _sequences.FindIndex(s => s.Id == id);
                if (index >= 0)
                {
                    deletedSequence = _sequences[index];
                    _sequences.RemoveAt(index);
                }
            }

            if (deletedSequence != null)
            {
                await SaveSequencesToFileAsync();
                await _logger.LogCommandAsync(new RobotCommand { Description = $"Command sequence '{deletedSequence.Name}' deleted" }, true);
                return true;
            }

            return false;
        }

        public async Task<bool> ExecuteSequenceAsync(int sequenceId, IRobotConnectionService robotService)
        {
            if (IsExecuting)
            {
                await _logger.LogErrorAsync("Cannot start sequence execution: another sequence is already running");
                return false;
            }

            var sequence = await GetSequenceByIdAsync(sequenceId);
            if (sequence == null)
            {
                await _logger.LogErrorAsync($"Sequence with ID {sequenceId} not found");
                return false;
            }

            if (!robotService.IsConnected)
            {
                var errorArgs = new CommandSequenceExecutionEventArgs
                {
                    Sequence = sequence,
                    IsSuccessful = false,
                    ErrorMessage = "Robot not connected"
                };
                SequenceExecutionError?.Invoke(this, errorArgs);
                return false;
            }

            _executionCancellationSource = new CancellationTokenSource();
            
            // Start execution in background
            _ = Task.Run(async () => await ExecuteSequenceInternalAsync(sequence, robotService, _executionCancellationSource.Token));
            
            return true;
        }

        public async Task<bool> StopSequenceExecutionAsync()
        {
            if (_executionCancellationSource != null && !_executionCancellationSource.Token.IsCancellationRequested)
            {
                _executionCancellationSource.Cancel();
                await _logger.LogCommandAsync(new RobotCommand { Description = "Command sequence execution stopped by user" }, true);
                return true;
            }
            
            return false;
        }

        private async Task ExecuteSequenceInternalAsync(CommandSequence sequence, IRobotConnectionService robotService, CancellationToken cancellationToken)
        {
            try
            {
                SequenceExecutionStarted?.Invoke(this, new CommandSequenceExecutionEventArgs
                {
                    Sequence = sequence,
                    IsSuccessful = true
                });

                await _logger.LogCommandAsync(new RobotCommand { Description = $"Starting execution of sequence '{sequence.Name}'" }, true);

                for (int i = 0; i < sequence.Steps.Count; i++)
                {
                    if (cancellationToken.IsCancellationRequested)
                    {
                        await _logger.LogCommandAsync(new RobotCommand { Description = $"Sequence '{sequence.Name}' execution cancelled" }, true);
                        return;
                    }

                    var step = sequence.Steps[i];
                    bool stepSuccessful = false;

                    try
                    {
                        stepSuccessful = await robotService.SendCommandAsync(step.Command);
                        
                        SequenceStepExecuted?.Invoke(this, new CommandSequenceStepEventArgs
                        {
                            Step = step,
                            StepIndex = i,
                            TotalSteps = sequence.Steps.Count,
                            IsSuccessful = stepSuccessful
                        });

                        if (!stepSuccessful)
                        {
                            throw new Exception($"Failed to send command: {step.Command.Description}");
                        }

                        // Wait for the specified delay
                        if (step.DelayAfterMs > 0)
                        {
                            await Task.Delay(step.DelayAfterMs, cancellationToken);
                        }
                    }
                    catch (OperationCanceledException)
                    {
                        await _logger.LogCommandAsync(new RobotCommand { Description = $"Sequence '{sequence.Name}' execution cancelled during step {i + 1}" }, true);
                        return;
                    }
                    catch (Exception ex)
                    {
                        var errorMessage = $"Error executing step {i + 1} of sequence '{sequence.Name}': {ex.Message}";
                        await _logger.LogErrorAsync(errorMessage, ex);
                        
                        SequenceStepExecuted?.Invoke(this, new CommandSequenceStepEventArgs
                        {
                            Step = step,
                            StepIndex = i,
                            TotalSteps = sequence.Steps.Count,
                            IsSuccessful = false,
                            ErrorMessage = ex.Message
                        });

                        SequenceExecutionError?.Invoke(this, new CommandSequenceExecutionEventArgs
                        {
                            Sequence = sequence,
                            IsSuccessful = false,
                            ErrorMessage = errorMessage
                        });
                        
                        return;
                    }
                }

                // Sequence completed successfully
                SequenceExecutionCompleted?.Invoke(this, new CommandSequenceExecutionEventArgs
                {
                    Sequence = sequence,
                    IsSuccessful = true
                });

                await _logger.LogCommandAsync(new RobotCommand { Description = $"Sequence '{sequence.Name}' completed successfully" }, true);
            }
            catch (Exception ex)
            {
                var errorMessage = $"Unexpected error during sequence execution: {ex.Message}";
                await _logger.LogErrorAsync(errorMessage, ex);
                
                SequenceExecutionError?.Invoke(this, new CommandSequenceExecutionEventArgs
                {
                    Sequence = sequence,
                    IsSuccessful = false,
                    ErrorMessage = errorMessage
                });
            }
            finally
            {
                _executionCancellationSource?.Dispose();
                _executionCancellationSource = null;
            }
        }

        private async Task LoadSequencesAsync()
        {
            if (!File.Exists(_sequencesFilePath))
            {
                await CreateDefaultSequencesAsync();
                return;
            }

            try
            {
                var json = await File.ReadAllTextAsync(_sequencesFilePath);
                if (!string.IsNullOrEmpty(json))
                {
                    var loadedSequences = JsonSerializer.Deserialize<List<CommandSequence>>(json);
                    if (loadedSequences != null)
                    {
                        lock (_lockObject)
                        {
                            _sequences.Clear();
                            _sequences.AddRange(loadedSequences);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync("Failed to load command sequences", ex);
                await CreateDefaultSequencesAsync();
            }
        }

        private async Task SaveSequencesToFileAsync()
        {
            try
            {
                List<CommandSequence> sequencesToSave;
                lock (_lockObject)
                {
                    sequencesToSave = new List<CommandSequence>(_sequences);
                }

                var json = JsonSerializer.Serialize(sequencesToSave, new JsonSerializerOptions
                {
                    WriteIndented = true
                });

                await File.WriteAllTextAsync(_sequencesFilePath, json);
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync("Failed to save command sequences", ex);
            }
        }

        private async Task CreateDefaultSequencesAsync()
        {
            // Create some example sequences
            var defaultSequences = new List<CommandSequence>();

            lock (_lockObject)
            {
                _sequences.Clear();
                _sequences.AddRange(defaultSequences);
            }

            await SaveSequencesToFileAsync();
        }
    }
}