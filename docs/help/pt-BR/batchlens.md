# BatchLens

**Demonstração sintética · não GxP · não usar para controle de processo, liberação ou
disposição de lotes.**

O BatchLens acompanha lotes de anticorpos da cultura de produção até a etapa de captura por
Proteína A e mostra, para cada lote, quanto produto havia em cada ponto e de onde vem cada
número. Todos os lotes aqui são sintéticos: feitos por um gerador, não medidos em planta alguma.

## Lotes

**Lotes** lista cada lote com seu produto, seu biorreator, início e fim, e uma marca no lote de
referência, aquele com que os outros são comparados. Abra um lote pelo seu identificador.

## Um lote

- **Execuções de fase**: o que aconteceu em qual ativo, e quando. Um lote é uma janela em
  equipamento compartilhado: o mesmo biorreator recebe um lote depois do outro.
- **Métricas**: cada uma com valor e unidade, estado, os motivos e os identificadores das
  entradas, ao lado do valor do lote de referência e da diferença.
- **Medições de pool**: o volume e a concentração por trás de cada massa de pool.
- **Tendências**: os sinais online do biorreator durante a fase de produção, lidos do
  PlantCraft, e a densidade de células viáveis e o título offline nos instantes de coleta.
- **Resultados de ensaio**: cada resultado com dois instantes, quando a amostra foi coletada e
  quando o resultado ficou disponível. Nunca são a mesma coisa.

## Como ler um estado

| Estado | Significado |
|---|---|
| Utilizável | Calculado a partir de entradas válidas |
| Suspeito | Calculado, mas uma entrada ou o resultado é implausível. O valor é mostrado, sinalizado |
| Insuficiente | Não calculado: falta algo necessário ou ainda não está disponível |
| Inválido | Não calculado: uma entrada viola uma regra (unidade errada, valor negativo) |

Uma métrica sem valor sempre diz por quê. Quando o PlantCraft não tem o ativo ou o sinal, o app
diz qual não encontrou em vez de desenhar uma tendência que não tem.

## Bom saber

- As massas são estimativas de concentração vezes volume; o método de ensaio é indicado.
- Unidades nunca são convertidas. Um valor em outra unidade é inválido.
- Os horários são mostrados no fuso da instalação, indicado em cada página.
- As fórmulas, suas premissas e as configurações estão em `docs/scientific-assumptions.md`
  do projeto.
